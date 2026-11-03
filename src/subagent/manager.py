"""Sub-agent manager — validates requests, runs one headless agent, and logs it.

Each sub-agent is a temporary :class:`Agent` created through the global
:class:`ChatManager`.  It runs one prompt to completion, emits the same event
stream as a chat, and is removed afterwards.  The full message history is
written to a chat-style JSON transcript beside the subagent skill.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from ..chat.manager import chat_manager
from ..util.error.types import SubAgentError
from .log import SubAgentLogWriter
from .models import SubAgentRecord, SubAgentSpec, SubAgentStatus

if TYPE_CHECKING:
    from ..app import ProcooApp

logger = logging.getLogger("procoo_qt")

_ALLOWED_TOOL_MODES = frozenset(("allow", "block"))


class SubAgentManager:
    """Runs headless sub-agents and writes their transcripts."""

    def __init__(self, app: ProcooApp) -> None:
        """Initialise the manager.

        Args:
            app: The backend application holding config and skill subsystems.
        """
        self._app = app
        self._semaphore: asyncio.Semaphore | None = None
        self._counter = 0

    # ------------------------------------------------------------------
    #  Public: Run
    # ------------------------------------------------------------------

    async def run(self, spec: SubAgentSpec) -> SubAgentRecord:
        """Run one sub-agent to completion and return its terminal record.

        Args:
            spec: The sub-agent request.

        Returns:
            The terminal record, including the log path when one was written.

        Raises:
            SubAgentError: When the prompt, skills, model, or tools are invalid.
        """
        self._validate_spec(spec)
        model_name = self._resolve_model(spec)
        activated = self._dedupe(spec.activated_skills)
        self._validate_skills(activated)
        activated = self._strip_subagent_skill(activated)
        tool_defs, tool_config = self._resolve_tools(spec, activated)

        record = SubAgentRecord(
            id=self._new_id(),
            status=SubAgentStatus.QUEUED,
            spec=spec,
            model_name=model_name,
            activated_skills=activated,
            tool_config=tool_config,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        logger.info(
            "Sub-agent '%s' started (model=%s, tools=%d)",
            record.id,
            model_name,
            len(tool_config),
        )
        await self._execute(record, model_name, activated, tool_defs, tool_config)
        return record

    # ------------------------------------------------------------------
    #  Private: Validation and resolution
    # ------------------------------------------------------------------

    def _validate_spec(self, spec: SubAgentSpec) -> None:
        """Validate top-level request fields.

        Args:
            spec: The request to validate.

        Raises:
            SubAgentError: When the prompt is empty or nesting is requested.
        """
        if not spec.prompt.strip():
            raise SubAgentError(
                brief="Sub-agent prompt is empty.",
                detail="Sub-agent requests require a non-empty 'prompt'.",
            )
        if spec.parent_id:
            raise SubAgentError(
                brief="Nested sub-agents are not supported.",
                detail="Sub-agent nesting is disabled; 'parent_id' must be empty.",
            )

    def _resolve_model(self, spec: SubAgentSpec) -> str:
        """Resolve and validate the model name for a request.

        Args:
            spec: The request whose model should be resolved.

        Returns:
            A configured model name.

        Raises:
            SubAgentError: When the requested model is not configured.
        """
        config = self._app.config
        model_name = spec.model or config.subagent_default_model or config.llm_model_name
        if model_name not in config.llm_models:
            available = ", ".join(config.llm_models)
            raise SubAgentError(
                brief=f"Unknown sub-agent model: {model_name}",
                detail=(f"Model '{model_name}' is not configured. Available models: {available}"),
            )
        return model_name

    def _validate_skills(self, skill_paths: list[str]) -> None:
        """Ensure every requested skill exists.

        Args:
            skill_paths: Skill paths to validate.

        Raises:
            SubAgentError: When a skill path is unknown.
        """
        manager = self._app.skill_manager
        missing = [path for path in skill_paths if manager.get_skill_by_path(path) is None]
        if missing:
            raise SubAgentError(
                brief=f"Unknown sub-agent skill: {', '.join(missing)}",
                detail=(
                    "These skill paths were not discovered under the skills "
                    f"directory: {', '.join(missing)}"
                ),
            )

    def _strip_subagent_skill(self, skill_paths: list[str]) -> list[str]:
        """Remove the subagent skill from a child request.

        Nesting is disabled, so a sub-agent never needs the skill that creates
        sub-agents.  Stripping it prevents the tool from appearing in the child
        prompt at all; the depth environment variable remains the hard guard.

        Args:
            skill_paths: Validated skill paths.

        Returns:
            The paths without the ``subagent`` skill.
        """
        manager = self._app.skill_manager
        kept: list[str] = []
        for path in skill_paths:
            info = manager.get_skill_by_path(path)
            if info is not None and info.name == "subagent":
                logger.info("Sub-agent request dropped nested skill '%s'", path)
                continue
            kept.append(path)
        return kept

    def _resolve_tools(
        self, spec: SubAgentSpec, activated: list[str]
    ) -> tuple[list[dict], dict[str, str]]:
        """Resolve tool definitions and per-tool modes.

        Args:
            spec: The request whose tools should be resolved.
            activated: Validated activated skill paths.

        Returns:
            A ``(tool_definitions, tool_config)`` tuple.

        Raises:
            SubAgentError: When a tool name or mode is invalid.
        """
        manager = self._app.skill_manager
        if spec.tools:
            requested = self._dedupe(spec.tools)
            tool_defs = manager.load_tool_functions_by_name(requested)
            resolved = {definition["name"] for definition in tool_defs}
            missing = [name for name in requested if name not in resolved]
            if missing:
                raise SubAgentError(
                    brief=f"Unknown sub-agent tool: {', '.join(missing)}",
                    detail=f"These tools were not discovered: {', '.join(missing)}",
                )
        else:
            tool_defs = manager.load_tool_functions(activated)

        selected = {definition["name"] for definition in tool_defs}
        unknown_modes = sorted(set(spec.tool_modes) - selected)
        if unknown_modes:
            raise SubAgentError(
                brief=f"Tool mode set for unselected tool: {', '.join(unknown_modes)}",
                detail=(
                    "tool_modes may only reference tools selected by 'tools' or "
                    f"the activated skills. Unselected: {', '.join(unknown_modes)}"
                ),
            )

        tool_config: dict[str, str] = {}
        for definition in tool_defs:
            name = definition["name"]
            mode = str(spec.tool_modes.get(name, "allow")).strip().lower()
            if mode not in _ALLOWED_TOOL_MODES:
                raise SubAgentError(
                    brief=f"Invalid sub-agent tool mode for '{name}': {mode}",
                    detail=("Headless sub-agents cannot ask for approval; use 'allow' or 'block'."),
                )
            tool_config[name] = mode
        return tool_defs, tool_config

    def _resolve_timeout(self, spec: SubAgentSpec) -> int:
        """Resolve and clamp the run timeout.

        Args:
            spec: The request whose timeout should be resolved.

        Returns:
            A positive timeout in seconds.
        """
        config = self._app.config
        timeout = spec.timeout or config.subagent_default_timeout
        return min(max(1, int(timeout)), config.subagent_max_timeout)

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        """Return non-empty strings with order preserved and duplicates removed.

        Args:
            values: Raw values from a request.

        Returns:
            A de-duplicated list.
        """
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            text = str(value).strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    # ------------------------------------------------------------------
    #  Private: Agent construction and execution
    # ------------------------------------------------------------------

    def _build_chat(
        self,
        chat_id: str,
        spec: SubAgentSpec,
        model_name: str,
        activated: list[str],
        tool_defs: list[dict],
        tool_config: dict[str, str],
    ) -> None:
        """Create the temporary headless agent for a sub-agent.

        Args:
            chat_id: Temporary chat id (equal to the sub-agent id).
            spec: The validated request.
            model_name: Resolved model name.
            activated: Activated skill paths.
            tool_defs: Resolved tool definitions.
            tool_config: Resolved tool modes.
        """
        config = self._app.config
        manager = self._app.skill_manager
        system_message = config.agent_system_prompt
        if spec.system_prompt.strip():
            system_message = f"{system_message}\n\n{spec.system_prompt.strip()}".strip()

        chat_manager.create_chat(
            chat_id=chat_id,
            model=config.llm_config(model_name),
            activated_skill_contents=manager.load_skill_contents(activated),
            tool_functions=tool_defs,
            tool_config=tool_config,
            skills_dir=config.skills_dir,
            system_message=system_message,
            summary_prompt=config.agent_summary_prompt,
            chat_limits={"max_bytes": 0, "max_tokens": 0},
            tool_env={
                "PROCOO_SUBAGENT_DEPTH": "1",
                "PROCOO_SUBAGENT_ID": chat_id,
            },
            media_dir=str(self._app.chat_store.storage_dir / "media"),
        )

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Return the concurrency semaphore, creating it on first use."""
        if self._semaphore is None:
            limit = max(1, self._app.config.subagent_max_concurrent)
            self._semaphore = asyncio.Semaphore(limit)
        return self._semaphore

    async def _execute(
        self,
        record: SubAgentRecord,
        model_name: str,
        activated: list[str],
        tool_defs: list[dict],
        tool_config: dict[str, str],
    ) -> None:
        """Run one sub-agent under the concurrency limit and write its log.

        Args:
            record: The queued record to execute.
            model_name: Resolved model name.
            activated: Activated skill paths.
            tool_defs: Resolved tool definitions.
            tool_config: Resolved tool modes.
        """
        agent = None
        try:
            async with self._get_semaphore():
                try:
                    self._build_chat(
                        record.id,
                        record.spec,
                        model_name,
                        activated,
                        tool_defs,
                        tool_config,
                    )
                except Exception as error:
                    logger.error("Sub-agent '%s' could not start: %s", record.id, error)
                    self._finish(
                        record,
                        SubAgentStatus.ERROR,
                        error=f"Failed to create sub-agent: {error}",
                    )
                    return

                agent = chat_manager.get_chat(record.id)
                if agent is None:
                    self._finish(
                        record,
                        SubAgentStatus.ERROR,
                        error="Sub-agent agent was not created.",
                    )
                    return
                await self._run_record(record, agent)
        except asyncio.CancelledError:
            self._finish(record, SubAgentStatus.CANCELLED, error="Sub-agent cancelled.")
            raise
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Sub-agent '%s' failed: %s", record.id, error)
            self._finish(record, SubAgentStatus.ERROR, error=str(error) or type(error).__name__)
        finally:
            with suppress(asyncio.CancelledError):
                await self._write_log(record, agent)
            chat_manager.remove_chat(record.id)

    async def _run_record(self, record: SubAgentRecord, agent: Any) -> None:
        """Drive the agent turn, apply the timeout, and store the result.

        Args:
            record: The record being executed.
            agent: The live headless agent.
        """
        record.status = SubAgentStatus.RUNNING
        timeout = self._resolve_timeout(record.spec)
        logger.info("Sub-agent '%s' running (timeout=%ss)", record.id, timeout)
        try:
            error_message = await asyncio.wait_for(self._consume(agent, record), timeout=timeout)
        except TimeoutError:
            self._finish(
                record,
                SubAgentStatus.ERROR,
                error=f"Sub-agent timed out after {timeout}s.",
            )
            return

        record.tokens = self._read_tokens(agent)
        text = self._last_assistant_text(agent)
        if error_message:
            self._finish(record, SubAgentStatus.ERROR, text=text, error=error_message)
        elif not text:
            self._finish(
                record,
                SubAgentStatus.ERROR,
                error="Sub-agent returned no assistant response.",
            )
        else:
            self._finish(record, SubAgentStatus.DONE, text=text)

    async def _consume(self, agent: Any, record: SubAgentRecord) -> str:
        """Run the agent turn and drain its event queue.

        Args:
            agent: The live headless agent.
            record: The record supplying the prompt.

        Returns:
            The last error brief, or an empty string on success.
        """
        task = asyncio.ensure_future(agent.run(record.spec.prompt, record.spec.images))
        error_message = ""
        try:
            while not task.done() or not agent.event_queue.empty():
                try:
                    event = await asyncio.wait_for(agent.event_queue.get(), timeout=0.1)
                except TimeoutError:
                    if not task.done():
                        continue
                    break
                error_message = self._handle_event(event, error_message)
            if not task.done():
                await task
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
            raise
        return error_message

    @staticmethod
    def _handle_event(event: dict, error_message: str) -> str:
        """Return the latest agent error brief from one event.

        Args:
            event: One agent event dict.
            error_message: The error brief accumulated so far.

        Returns:
            The updated error brief.
        """
        if event.get("type") == "error":
            return str(event.get("brief") or event.get("detail") or "Agent error")
        return error_message

    @staticmethod
    def _read_tokens(agent: Any) -> dict:
        """Return the agent's token counters.

        Args:
            agent: The live headless agent.

        Returns:
            A ``{"input": int, "output": int}`` mapping.
        """
        return {
            "input": int(getattr(agent, "api_input_latest", 0) or 0),
            "output": int(getattr(agent, "api_output_sum", 0) or 0),
        }

    @staticmethod
    def _last_assistant_text(agent: Any) -> str:
        """Return the last non-empty assistant message text.

        Args:
            agent: The live headless agent.

        Returns:
            The assistant text, or an empty string.
        """
        for message in reversed(agent.messages):
            if message.get("role") != "assistant":
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                text = "".join(parts).strip()
                if text:
                    return text
        return ""

    # ------------------------------------------------------------------
    #  Private: Logging
    # ------------------------------------------------------------------

    async def _write_log(self, record: SubAgentRecord, agent: Any) -> None:
        """Write the run transcript, tolerating cancellation and I/O errors.

        Args:
            record: The terminal record.
            agent: The live agent, or ``None`` when construction failed.
        """
        messages = list(agent.messages) if agent is not None else []
        if agent is not None and not record.tokens:
            record.tokens = self._read_tokens(agent)
        writer = self._log_writer()
        try:
            record.log_path = await asyncio.to_thread(writer.write, record, messages)
        except asyncio.CancelledError:
            try:
                record.log_path = writer.write(record, messages)
            except Exception as error:
                logger.error("Could not write sub-agent log for '%s': %s", record.id, error)
            raise
        except Exception as error:
            logger.error("Could not write sub-agent log for '%s': %s", record.id, error)

    def _log_writer(self) -> SubAgentLogWriter:
        """Resolve the log directory inside the subagent skill.

        Returns:
            A writer targeting ``references/logs`` under the subagent skill.
        """
        manager = self._app.skill_manager
        info = next((skill for skill in manager.skills if skill.name == "subagent"), None)
        if info is None:
            info = manager.get_skill_by_path("basic/subagent")
        root = Path(manager.skills_dir)
        if info is not None:
            log_dir = root / info.path / "references" / "logs"
        else:
            log_dir = root / "basic" / "subagent" / "references" / "logs"
        return SubAgentLogWriter(log_dir)

    # ------------------------------------------------------------------
    #  Private: Record lifecycle
    # ------------------------------------------------------------------

    def _finish(
        self,
        record: SubAgentRecord,
        status: SubAgentStatus,
        *,
        text: str | None = None,
        error: str | None = None,
    ) -> None:
        """Apply a terminal state to a record.

        Args:
            record: The record to update.
            status: The terminal status.
            text: Final assistant text, when available.
            error: Error brief, when the run failed.
        """
        record.status = status
        record.finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
        if text is not None:
            record.text = text
        if error is not None:
            record.error = error
        logger.info("Sub-agent '%s' finished with %s", record.id, status)

    def _new_id(self) -> str:
        """Return a unique sub-agent id."""
        self._counter += 1
        return f"subagent:{time.strftime('%Y%m%d_%H%M%S')}:{self._counter}"
