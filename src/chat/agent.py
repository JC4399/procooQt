"""Agent runtime — ReAct loop, tool execution, and event streaming.

Unified agent class that combines conversation memory, LLM reasoning,
subprocess tool execution, tool-approval workflow, and UI event streaming
into a single class — no wrapper layers.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import json
import logging
from pathlib import Path
import traceback
from typing import Any, cast

from .llm import (
    LLMResponse,
    OpenAIModel,
)
from .media import MediaStore

logger = logging.getLogger("procoo_qt")


def _strip_internal_keys(value: Any) -> Any:
    """Recursively drop internal ``_``-prefixed keys from a message payload.

    Strict providers (e.g. Mistral via OpenRouter) reject unknown fields
    inside ``tool_calls``, so internal metadata such as ``_mode`` and
    ``_streaming_tool_calls`` must be removed before the request is sent.
    The input is never mutated; nested dicts and lists are deep-copied.

    Args:
        value: A message dict, list, or scalar from ``self.messages``.

    Returns:
        A deep copy with all ``_``-prefixed keys removed.
    """
    if isinstance(value, dict):
        return {k: _strip_internal_keys(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [_strip_internal_keys(item) for item in value]
    return value


# ------------------------------------------------------------------
#  Agent
# ------------------------------------------------------------------


class Agent:
    """Unified agent that handles reasoning, tool execution, and event streaming.

    Conversation state is a single ``self.messages`` list of
    OpenAI-compatible dicts with ``_``-prefixed metadata keys
    (``reasoning_content`` on assistant, ``_mode`` on tool_calls).  The UI
    renders from it directly; before each LLM call the ``_``-prefixed keys
    are stripped so strict providers accept the request.

    Attributes:
        chat_id: Unique identifier for this chat.
        event_queue: ``asyncio.Queue`` of UI events produced during generation.
        messages: Conversation history in OpenAI-compatible format with ``_``
            prefixed metadata keys (``reasoning_content`` on assistant, ``_mode`` on
            tool_calls).
        activated_skills: Names of activated (fully loaded) skills.
        sys_prompt: Full system prompt including all skill instructions.
    """

    def __init__(
        self,
        chat_id: str,
        model: dict,
        activated_skill_contents: list[dict],
        tool_functions: list[dict],
        tool_config: dict[str, str],
        skills_dir: str,
        system_message: str = "You are a helpful assistant.",
        sampling_config: dict | None = None,
        initial_messages: list[dict] | None = None,
        summary_prompt: str = "",
        chat_limits: dict | None = None,
        tool_env: dict[str, str] | None = None,
        media_dir: str = "",
    ) -> None:
        """Initialise the agent.

        Args:
            chat_id: Unique chat identifier.
            model: LLM configuration dict (model_name, api_key, api_base).
            activated_skill_contents: List of skill-content dicts for activated skills.
            tool_functions: List of tool-definition dicts (name, script_path, …).
            tool_config: Per-tool mode mapping (``"allow"``, ``"ask"``, ``"block"``).
            skills_dir: Path to the skills directory.
            system_message: Base system prompt for the agent.
            sampling_config: Optional LLM sampling parameters.
            initial_messages: Optional list of role/content dicts to seed
                the conversation history with.
            summary_prompt: Instruction used when summarizing an over-limit chat.
            chat_limits: Optional ``{"max_bytes": int, "max_tokens": int}``
                compaction limits (``0`` or a negative value disables the
                corresponding limit).
            tool_env: Optional environment variables added to every tool
                subprocess (used by sub-agents to propagate depth/id).
            media_dir: Optional root directory for disk-backed multimodal
                media. When empty, images stay inline as data URLs.
        """
        from ..util.log.formatter import log_chat_skills
        from ..util.tokens.tracker import ChatTokenTracker

        self.chat_id = chat_id
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._pending_approvals: dict[str, asyncio.Queue] = {}
        self.messages: list[dict] = list(initial_messages) if initial_messages else []
        self._media_store = MediaStore(media_dir) if media_dir else None
        self._tool_config: dict[str, str] = dict(tool_config)
        self._tool_env: dict[str, str] = dict(tool_env or {})
        self._current_assistant_msg: dict | None = None
        self.skills_dir = skills_dir
        self.activated_skills = [s.get("path", "") for s in activated_skill_contents]
        self.activated_skill_contents: list[dict] = list(activated_skill_contents)
        self._tool_defs: list[dict] = list(tool_functions) if tool_functions else []
        self._pending_sys_message: str = ""
        self._committed_activated: set[str] = set(self.activated_skills)

        self._base_system_message = system_message
        self.sys_prompt = self._build_sys_prompt(activated_skill_contents)

        self._tokens = ChatTokenTracker(self.sys_prompt)

        self._model = self._build_model(model or {})

        self._tools: dict[str, dict] = {}
        for td in self._tool_defs:
            self._tools[td["name"]] = td

        self._prev_api_input: int = 0
        self.api_input_latest: int = 0
        self.api_output_sum: int = 0
        self._estimated_total: int = 0
        self._estimated_bytes: int = 0

        self.summary_prompt = summary_prompt
        limits = chat_limits or {}
        self._max_bytes: int = int(limits.get("max_bytes", 0) or 0)
        self._max_tokens: int = int(limits.get("max_tokens", 0) or 0)

        log_chat_skills(self.activated_skills, self._tool_defs)

    # ------------------------------------------------------------------
    #  Public: Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _build_model(model: dict) -> OpenAIModel:
        """Build the LLM client from a model config dict.

        Args:
            model: LLM config dict (``model_name``, ``api_key``, ``api_base``).

        Returns:
            A streaming :class:`OpenAIModel`.
        """
        return OpenAIModel(
            model_name=model.get("model_name", "qwen2.5"),
            api_key=model.get("api_key", "ollama"),
            client_kwargs={"base_url": model.get("api_base", "http://localhost:11434/v1")},
            stream=True,
        )

    def set_model(self, model: dict) -> None:
        """Replace the LLM client used for subsequent turns.

        Args:
            model: LLM config dict (``model_name``, ``api_key``, ``api_base``).
        """
        self._model = self._build_model(model or {})

    def update_skill_config(
        self,
        activated_skill_contents: list[dict],
        tool_functions: list[dict],
        tool_config: dict[str, str],
    ) -> dict:
        """Push new skill/tool configuration to the live agent.

        Before the first user message the configuration is freely adjustable:
        the system prompt and tool set are rebuilt to match the new config
        exactly, so skills can be removed as well as added.  Once the chat has
        started, only a delta is applied — new context is accumulated into an
        internal buffer that is injected as a system message immediately before
        the next user message, and removals only produce warnings.

        Returns:
            dict with ``warnings`` (list[str]), ``added_activated`` (list[str]),
            ``added_tools`` (list[str]), and ``pending_sys_message`` (str).
        """
        chat_started = any(m.get("role") == "user" for m in self.messages)
        if not chat_started:
            return self._replace_skill_config(
                activated_skill_contents,
                tool_functions,
                tool_config,
            )
        return self._apply_skill_delta(
            activated_skill_contents,
            tool_functions,
            tool_config,
        )

    def _replace_skill_config(
        self,
        activated_skill_contents: list[dict],
        tool_functions: list[dict],
        tool_config: dict[str, str],
    ) -> dict:
        """Rebuild the prompt and tool set to exactly match the given config.

        Used before the first user message, when nothing has been committed to
        the conversation history yet.

        Args:
            activated_skill_contents: New activated skill contents.
            tool_functions: New tool definition dicts.
            tool_config: New per-tool mode mapping.

        Returns:
            An empty delta result (no warnings or additions).
        """
        new_activated_names = {s.get("path", "") for s in activated_skill_contents}

        self.sys_prompt = self._build_sys_prompt(activated_skill_contents)
        self._tokens.update_sys_prompt(self.sys_prompt)
        self._pending_sys_message = ""
        self._committed_activated = set(new_activated_names)
        self._tools = {td["name"]: td for td in tool_functions}
        self.activated_skills = list(new_activated_names)
        self.activated_skill_contents = list(activated_skill_contents)
        self._tool_defs = list(tool_functions) if tool_functions else []
        self.set_tool_config(tool_config)

        return {
            "warnings": [],
            "added_activated": [],
            "added_tools": [],
            "pending_sys_message": "",
        }

    def _apply_skill_delta(
        self,
        activated_skill_contents: list[dict],
        tool_functions: list[dict],
        tool_config: dict[str, str],
    ) -> dict:
        """Apply a post-start skill/tool delta, warning on removals.

        Args:
            activated_skill_contents: New activated skill contents.
            tool_functions: New tool definition dicts.
            tool_config: New per-tool mode mapping.

        Returns:
            dict with ``warnings``, ``added_activated``, ``added_tools``, and
            ``pending_sys_message``.
        """
        warnings: list[str] = []
        added_activated: list[str] = []
        added_tools: list[str] = []

        new_activated_names = {s.get("path", "") for s in activated_skill_contents}

        removed_from_activated = self._committed_activated - new_activated_names

        if removed_from_activated:
            warnings.append(
                f"Skills removed from activated: {', '.join(sorted(removed_from_activated))}. "
                "Their instructions and tools remain in the conversation history "
                "and cannot be removed."
            )

        pending_activated = new_activated_names - self._committed_activated

        additions: list[str] = []

        for skill in activated_skill_contents:
            spath = skill.get("path", "")
            if spath in pending_activated:
                instructions = skill.get("instructions", "")
                if instructions:
                    additions.append(instructions)
                if spath:
                    abs_skill_dir = (Path(self.skills_dir) / spath).resolve()
                    additions.append(f"[Skill directory: `{abs_skill_dir}/`]")
                added_activated.append(spath)

        if additions:
            self._pending_sys_message = "\n\n".join(additions)
        else:
            self._pending_sys_message = ""

        old_tool_names = {td.get("name", "") for td in self._tool_defs}
        for td in tool_functions:
            tname = td.get("name", "")
            if tname not in old_tool_names:
                self._tools[tname] = td
                added_tools.append(tname)

        self.activated_skills = list(new_activated_names)
        self.activated_skill_contents = list(activated_skill_contents)
        self._tool_defs = list(tool_functions) if tool_functions else []

        self.set_tool_config(tool_config)

        return {
            "warnings": warnings,
            "added_activated": added_activated,
            "added_tools": added_tools,
            "pending_sys_message": self._pending_sys_message,
        }

    # ------------------------------------------------------------------
    #  Public: Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        message_content: str,
        images: list[str] | None = None,
    ) -> None:
        """Execute one user turn and stream events to the UI.

        Messages are appended to ``self.messages`` in OpenAI-compatible
        format as the turn progresses.

        Args:
            message_content: The user's text message.
            images: Optional list of data-URL strings (e.g.
                ``"data:image/webp;base64,..."``). When provided, the first
                user message is built as a multimodal content list (text part
                followed by ``image_url`` parts) so a multimodal model sees
                the images on its very first reasoning step.
        """
        self._prev_api_input = 0
        self.api_input_latest = 0
        self.api_output_sum = 0

        try:
            if self._pending_sys_message:
                pending = self._pending_sys_message.strip()
                self._pending_sys_message = ""
                self.messages.append(
                    {"role": "system", "content": pending},
                )
                self._committed_activated = set(self.activated_skills)

            if images:
                content_parts: list[dict] = []
                text = message_content or ""
                if text:
                    content_parts.append({"type": "text", "text": text})
                for url in images:
                    if not url:
                        continue
                    if self._media_store is not None:
                        url = self._media_store.store_data_url(self.chat_id, url)
                    content_parts.append(
                        {"type": "image_url", "image_url": {"url": url}},
                    )
                if not content_parts:
                    content_parts = [{"type": "text", "text": ""}]
                self.messages.append({"role": "user", "content": content_parts})
                logger.info(
                    "Agent[%s] seeded user message with %d image(s)",
                    self.chat_id,
                    len(images),
                )
            else:
                self.messages.append({"role": "user", "content": message_content or ""})

            await self._run_react_loop()

            await self.refresh_estimated()

            await self._emit_event({"type": "done", "chat_id": self.chat_id})

        except asyncio.CancelledError:
            logger.warning("Agent[%s] cancelled by user", self.chat_id)
            await self._emit_event(
                {
                    "type": "error",
                    "brief": "Generation cancelled",
                    "detail": "Generation cancelled by user.",
                    "category": "agent",
                }
            )
        except Exception as e:
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            detail = "".join(tb)
            logger.error("Agent[%s] error: %s", self.chat_id, detail)
            await self._emit_event(
                {
                    "type": "error",
                    "brief": str(e) or type(e).__name__,
                    "detail": detail,
                    "category": "agent",
                }
            )

    # ------------------------------------------------------------------
    #  Private: ReAct loop
    # ------------------------------------------------------------------

    async def _run_react_loop(self) -> None:
        """Alternate reasoning and tool execution indefinitely.

        Breaks when the model produces a text response without tool
        calls.
        """
        while True:
            self._current_assistant_msg = None
            tool_blocks = await self._reasoning()
            if not tool_blocks:
                return
            await self._resolve_tool_calls(tool_blocks)

    # ------------------------------------------------------------------
    #  Private: Tool resolution
    # ------------------------------------------------------------------

    async def _resolve_tool_calls(self, tool_blocks: list[dict]) -> None:
        """Register tool calls, collect approvals, then execute concurrently.

        Phase 1 — register all tool_call structs on the assistant message
        and emit tool_call events.  Phase 2 — concurrently await approval
        decisions for ask-mode tools.  Phase 3 — concurrently execute all
        approved tools.  Phase 4 — record results in original call order.

        Args:
            tool_blocks: Tool_use block dicts from the model response.
        """
        current_msg = self._ensure_current_assistant()

        task_list: list[dict] = []
        for tb in tool_blocks:
            tool_id = tb["id"]
            tool_name = tb["name"]
            tool_args_raw = tb.get("input", "{}")
            parse_error: str | None = None
            if isinstance(tool_args_raw, str):
                try:
                    tool_args = json.loads(tool_args_raw)
                    if not isinstance(tool_args, (dict, list)):
                        tool_args = {}
                except json.JSONDecodeError, TypeError:
                    logger.warning(
                        "Failed to parse tool args for '%s' (id=%s): %s...",
                        tool_name,
                        tool_id,
                        tool_args_raw[:100],
                    )
                    tool_args = {}
                    parse_error = (
                        f"Tool '{tool_name}' received invalid arguments. "
                        f"Expected JSON, got: {tool_args_raw[:200]}"
                    )
            else:
                tool_args = tool_args_raw if isinstance(tool_args_raw, (dict, list)) else {}

            if isinstance(tool_args, dict) and tool_name in self._tools:
                self._strip_empty_optional_args(tool_args, tool_name)
            mode = self._tool_config.get(tool_name, "ask")

            openai_tc = {
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_args),
                },
                "_mode": mode,
            }
            current_msg.setdefault("tool_calls", []).append(openai_tc)

            task = {
                "id": tool_id,
                "name": tool_name,
                "args": tool_args,
                "mode": mode,
            }
            if parse_error is not None:
                task["_parse_error"] = parse_error
            task_list.append(task)

        current_msg.pop("_streaming_tool_calls", None)

        for t in task_list:
            logger.info("TOOL: id=%s name=%s args=%s", t["id"], t["name"], t["args"])
            await self._emit_event(
                {
                    "type": "tool_call",
                    "id": t["id"],
                    "name": t["name"],
                    "arguments": t["args"],
                    "mode": t["mode"],
                }
            )

        async def _get_decision(t: dict) -> tuple[str, str | None]:
            if t["mode"] == "block":
                return (
                    "deny",
                    f"Tool '{t['name']}' is blocked by user in current configuration.",
                )
            if t["mode"] == "allow":
                return ("approve", None)
            return await self._wait_for_approval(t["id"])

        decisions = await asyncio.gather(
            *[_get_decision(t) for t in task_list],
            return_exceptions=True,
        )

        async def _execute_one(t: dict, decision) -> tuple[str, bool, list[dict] | None]:
            parse_error = t.get("_parse_error")
            if parse_error is not None:
                return (parse_error, True, None)
            if isinstance(decision, BaseException):
                result = f"Tool '{t['name']}' approval error: {decision}"
                return (result, True, None)
            decision_type, denial_reason = decision
            if decision_type == "deny":
                result = "Tool execution denied by user."
                if denial_reason:
                    result += f"\nUser feedback: {denial_reason}"
                return (result, False, None)
            result = await self.run_tool(t["name"], t["args"])
            return self._parse_tool_media(result)

        results = await asyncio.gather(
            *[_execute_one(t, dec) for t, dec in zip(task_list, decisions, strict=True)],
            return_exceptions=True,
        )

        all_media: list[dict] = []
        for t, result in zip(task_list, results, strict=True):
            if isinstance(result, BaseException):
                await self._record_tool_result(
                    t["id"], t["name"], f"Tool execution error: {result}", is_error=True
                )
            else:
                content, is_error, media_list = result
                await self._record_tool_result(t["id"], t["name"], content, is_error=is_error)
                if media_list:
                    all_media.extend(media_list)

        if all_media:
            await self._inject_media_user_message(all_media)

    # ------------------------------------------------------------------
    #  Private: Reasoning step
    # ------------------------------------------------------------------

    async def _reasoning(self) -> list[dict]:
        """Perform one LLM call with the current conversation.

        Builds the prompt from ``self.messages``, streams the response,
        and writes text/thinking to ``self.messages`` via the shared
        block processor.

        Returns:
            List of tool_use block dicts from the model response, or an
            empty list if the model produced a text response.
        """
        prompt = self._build_prompt(self.messages)
        tools = self._build_tool_schemas() if self._tools else None
        res = await self._model(prompt, tools=tools)

        tool_blocks: list[dict] = []
        last_usage = None
        if self._model.stream:
            async for chunk in cast(AsyncGenerator, res):
                tool_blocks = await self._process_blocks(chunk.content)
                if chunk.usage:
                    last_usage = chunk.usage
                await asyncio.sleep(0)
        else:
            cr = cast(LLMResponse, res)
            tool_blocks = await self._process_blocks(cr.content)
            last_usage = cr.usage

        if last_usage:
            self.api_output_sum += last_usage.output_tokens
            self._prev_api_input = self.api_input_latest
            self.api_input_latest = last_usage.input_tokens
            await self._emit_event(
                {
                    "type": "token_usage",
                    "input": last_usage.input_tokens,
                    "output": last_usage.output_tokens,
                    "output_cumulative": self.api_output_sum,
                    "input_previous": self._prev_api_input,
                }
            )

        return tool_blocks

    # ------------------------------------------------------------------
    #  Private: Tool execution
    # ------------------------------------------------------------------

    async def _record_tool_result(
        self,
        tool_id: str,
        tool_name: str,
        result: str,
        *,
        is_error: bool = False,
    ) -> None:
        """Emit a tool_result event and append to ``self.messages``."""
        await self._emit_event(
            {
                "type": "tool_result",
                "id": tool_id,
                "name": tool_name,
                "content": result,
                "is_error": is_error,
            }
        )
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result,
                "name": tool_name,
            }
        )

    async def _wait_for_approval(self, tool_id: str) -> tuple[str, str | None]:
        """Await user decision for a pending tool call.

        Returns:
            A tuple of ``("approve"|"deny", denial_reason|None)``.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._pending_approvals[tool_id] = queue
        try:
            return await queue.get()
        finally:
            self._pending_approvals.pop(tool_id, None)

    async def run_tool(self, tool_name: str, tool_args: dict | list) -> str:
        """Execute a registered tool via subprocess.

        Args:
            tool_name: The name key of the registered tool definition.
            tool_args: JSON-serialisable dict of arguments passed to the
                tool script via stdin.

        Returns:
            The tool's stdout output as a string, or an error/timeout
            message.
        """
        from ..util.venv import build_tool_env, resolve_tool_python

        td = self._tools[tool_name]
        script_path = td["script_path"]
        args_json = json.dumps(tool_args, ensure_ascii=False)

        tool_python = resolve_tool_python()
        proc = await asyncio.create_subprocess_exec(
            tool_python,
            script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=build_tool_env(tool_python, extra_env=self._tool_env),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(args_json.encode("utf-8")),
                timeout=td.get("timeout", 600),
            )
        except TimeoutError:
            proc.kill()
            return f"Tool '{tool_name}' timed out after {td.get('timeout', 600)}s."

        output = stdout.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        stderr_output = stderr.decode("utf-8", errors="replace").strip() if stderr else ""
        if proc.returncode is not None and proc.returncode != 0:
            err_detail = stderr_output or output.strip()
            return f"Tool '{tool_name}' exited with code {proc.returncode}. {err_detail[:1000]}"
        if stderr_output:
            output += f"\n[stderr]\n{stderr_output}"
        return output.strip() or "(no output)"

    @staticmethod
    def _parse_tool_media(result: str) -> tuple[str, bool, list[dict] | None]:
        """Parse a tool result string for the ``_media`` marker.

        When a tool returns JSON with ``_media: true`` (e.g. image/pdf-image
        modes), the result contains base64 images that must be injected as
        a user message instead of a tool result.

        Args:
            result: Raw stdout string from the tool subprocess.

        Returns:
            Tuple of ``(text_content, is_error, media_list_or_none)``.
        """
        try:
            data = json.loads(result)
            if isinstance(data, dict) and data.get("_media"):
                text = data.get("text", "")
                media = data.get("media", [])
                if isinstance(media, list):
                    return (text, False, media)
        except json.JSONDecodeError, TypeError:
            pass
        return (result, False, None)

    async def _inject_media_user_message(self, media_list: list[dict]) -> None:
        """Inject a multimodal user message carrying images into the conversation.

        Appends a user message with ``image_url`` content parts to
        ``self.messages`` so the LLM can see the images on the next
        reasoning step.

        Args:
            media_list: List of ``{"desc": str, "data": base64_str}`` entries
                from the tool subprocess output.
        """
        content_parts: list[dict] = []
        for m in media_list:
            desc = m.get("desc", "[IMAGE]")
            b64_data = m.get("data", "")
            if not b64_data:
                continue
            content_parts.append({"type": "text", "text": f"[IMAGE: {desc}]"})
            url = f"data:image/png;base64,{b64_data}"
            if self._media_store is not None:
                url = self._media_store.store_data_url(self.chat_id, url)
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": url},
                }
            )
        if not content_parts:
            return
        user_msg: dict = {"role": "user", "content": content_parts}
        self.messages.append(user_msg)
        await self._emit_event(
            {
                "type": "media_user_message",
                "count": len(media_list),
            }
        )
        logger.info(
            "Agent[%s] injected media user message (%d images)",
            self.chat_id,
            len(media_list),
        )

    # ------------------------------------------------------------------
    #  Private: Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(self, messages: list[dict], *, suffix: str | None = None) -> list[dict]:
        """Build the prompt list for an LLM call.

        Args:
            messages: Conversation history dicts.
            suffix: Optional user message appended after the history.

        Returns:
            List of role/content dicts ready for the model, with internal
            ``_``-prefixed keys stripped and media references expanded.
        """
        prompt = [{"role": "system", "content": self.sys_prompt}]
        for message in messages:
            clean = _strip_internal_keys(message)
            if self._media_store is not None:
                self._media_store.expand_message(clean)
            prompt.append(clean)
        if suffix:
            prompt.append({"role": "user", "content": suffix})
        return prompt

    async def _process_blocks(self, blocks: list[dict]) -> list[dict]:
        """Process content blocks from a model response chunk.

        Emits UI events and writes text/thinking metadata into the
        current assistant message in ``self.messages``.

        Also writes incremental tool_use blocks into
        ``_streaming_tool_calls`` on the assistant message so the UI can
        render argument streaming before execution begins.

        Args:
            blocks: Content block dicts from ``LLMResponse.content``.

        Returns:
            Tool_use blocks found in this chunk (empty list if none).
        """
        tool_blocks: list[dict] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "thinking":
                thinking_text = block.get("thinking", "")
                await self._emit_event({"type": "thinking", "text": thinking_text})
                self._handle_thinking(thinking_text)
            elif btype == "response":
                response_text = block.get("response", "")
                await self._emit_event({"type": "message", "text": response_text})
                self._handle_response_text(response_text)
            elif btype == "tool_use":
                tool_blocks.append(block)

        # ------------------------------------------------------------------
        #  Write streaming tool_calls so the UI can render argument streaming
        # ------------------------------------------------------------------
        if tool_blocks:
            current = self._ensure_current_assistant()
            streaming_calls = []
            for tb in tool_blocks:
                raw_input = tb.get("input", "")
                if not isinstance(raw_input, str):
                    raw_input = json.dumps(raw_input)
                streaming_calls.append(
                    {
                        "id": tb.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tb.get("name", ""),
                            "arguments": raw_input,
                        },
                        "_mode": self._tool_config.get(tb.get("name", ""), "ask"),
                    }
                )
            current["_streaming_tool_calls"] = streaming_calls
            await self._emit_event({"type": "tool_call_streaming"})

        return tool_blocks

    # ------------------------------------------------------------------
    #  Private: Builders
    # ------------------------------------------------------------------

    def _build_tool_schemas(self) -> list[dict]:
        """Build OpenAI-compatible tool schema dicts from registered tools."""
        schemas = []
        for name, td in self._tools.items():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": td.get("description", ""),
                        "parameters": td.get(
                            "parameters",
                            {
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        ),
                    },
                }
            )
        return schemas

    def _strip_empty_optional_args(self, tool_args: dict, tool_name: str) -> None:
        """Strip empty-list and empty-dict values from optional tool parameters.

        Uses the stored tool schema to check which parameters are optional
        (not listed in ``required``).  Mutates ``tool_args`` in place.

        Args:
            tool_args: Parsed tool argument dict from the model.
            tool_name: Name of the tool for schema lookup.
        """
        td = self._tools.get(tool_name)
        if td is None:
            return
        params_schema = td.get("parameters", {})
        properties = params_schema.get("properties", {})
        required = set(params_schema.get("required", []))
        for key in list(tool_args.keys()):
            if key in properties and key not in required and tool_args[key] in ([], {}):
                del tool_args[key]

    def _build_sys_prompt(self, activated_skill_contents: list[dict]) -> str:
        """Build the full system prompt from the base message and skill contents.

        Args:
            activated_skill_contents: List of skill dicts whose full instructions
                are embedded in the prompt.

        Returns:
            The assembled system prompt string.
        """
        prompt = self._base_system_message
        for skill in activated_skill_contents:
            prompt += f"\n\n{skill.get('instructions', '')}"
            spath = skill.get("path", "")
            if spath:
                abs_skill_dir = (Path(self.skills_dir) / spath).resolve()
                prompt += f"\n[Skill directory: `{abs_skill_dir}/`]"
        return prompt

    # ------------------------------------------------------------------
    #  Private: Event helpers
    # ------------------------------------------------------------------

    async def _emit_event(self, event: dict) -> None:
        await self.event_queue.put(event)

    # ------------------------------------------------------------------
    #  Token / size accounting
    # ------------------------------------------------------------------

    async def refresh_estimated(self) -> None:
        """Recompute cached chat token and byte estimates (offloaded).

        Runs the word-count total and JSON byte-size computations in a
        worker thread so the UI event loop never blocks.
        """
        self._estimated_total = await self._tokens.compute_total_async(self.messages)
        self._estimated_bytes = await self._tokens.compute_bytes_async(self.messages)

    def chat_token_count(self) -> int:
        """Return the canonical chat token count.

        Uses the latest true API input-token count when available,
        otherwise falls back to the cached word-count estimate.
        """
        if self.api_input_latest > 0:
            return self.api_input_latest
        return self._estimated_total

    def chat_byte_size(self) -> int:
        """Return the cached JSON byte size of the message history."""
        return self._estimated_bytes

    # ------------------------------------------------------------------
    #  Chat compaction
    # ------------------------------------------------------------------

    def check_limit_exceeded(self) -> dict | None:
        """Return limit info when the chat exceeds a configured limit.

        Checks the JSON byte size against ``max_bytes`` and the token
        count against ``max_tokens``.  A limit of ``0`` or a negative
        value disables that check.

        Returns:
            Dict with ``reason`` (``"bytes"``/``"tokens"``), ``bytes`` and
            ``tokens`` when exceeded, otherwise ``None``.
        """
        tokens = self.chat_token_count()
        if self._max_tokens > 0 and tokens > self._max_tokens:
            return {"reason": "tokens", "bytes": self.chat_byte_size(), "tokens": tokens}
        if self._max_bytes > 0 and self.chat_byte_size() > self._max_bytes:
            return {"reason": "bytes", "bytes": self.chat_byte_size(), "tokens": tokens}
        return None

    async def summarize(self) -> str:
        """Summarize the current conversation in a single non-tool LLM call.

        Returns:
            The summary text, or an empty string on failure.
        """
        if not self.messages:
            return ""

        prompt = [
            {"role": "system", "content": self.summary_prompt},
            {"role": "user", "content": self._render_messages_for_summary()},
        ]

        response_text = ""
        try:
            res = await self._model(prompt, tools=None)
            if self._model.stream:
                async for chunk in cast(AsyncGenerator, res):
                    for block in chunk.content:
                        if isinstance(block, dict) and block.get("type") == "response":
                            response_text = block.get("response", "") or response_text
                    await asyncio.sleep(0)
            else:
                cr = cast(LLMResponse, res)
                for block in cr.content:
                    if isinstance(block, dict) and block.get("type") == "response":
                        response_text = block.get("response", "") or response_text
        except Exception as e:
            logger.error("Agent[%s] summarization failed: %s", self.chat_id, e)

        return response_text.strip()

    def _render_messages_for_summary(self) -> str:
        """Serialize the message history into a compact role-labelled text block."""
        lines: list[str] = []
        for msg in self.messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            if content:
                lines.append(f"[{role}]\n{content}")
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                lines.append(f"[{role} tool_call {fn.get('name', '')}]\n{fn.get('arguments', '')}")
        return "\n\n".join(lines)

    # ------------------------------------------------------------------
    #  Private: Message helpers
    # ------------------------------------------------------------------

    def set_tool_config(self, tool_config: dict[str, str]) -> None:
        self._tool_config = dict(tool_config)

    def _ensure_current_assistant(self) -> dict:
        """Return the current assistant message dict, creating one if needed."""
        if self._current_assistant_msg is None:
            new_msg: dict = {"role": "assistant", "content": ""}
            self.messages.append(new_msg)
            self._current_assistant_msg = new_msg
        return self._current_assistant_msg

    def _handle_thinking(self, thinking_text: str) -> None:
        current = self._ensure_current_assistant()
        current["reasoning_content"] = thinking_text

    def _handle_response_text(self, text: str) -> None:
        current = self._ensure_current_assistant()
        current["content"] = text

    # ------------------------------------------------------------------
    #  Public: Tool approval
    # ------------------------------------------------------------------

    async def approve_tool(self, tool_call_id: str) -> None:
        if tool_call_id in self._pending_approvals:
            await self._pending_approvals[tool_call_id].put(("approve", None))

    async def deny_tool(self, tool_call_id: str, denial_reason: str = "") -> None:
        if tool_call_id in self._pending_approvals:
            await self._pending_approvals[tool_call_id].put(("deny", denial_reason))
