"""Sub-agent manager — validates requests, runs headless agents, and tracks results.

Each sub-agent is a temporary :class:`Agent` created through the global
:class:`ChatManager`.  It runs one prompt to completion, emits the same event
stream as a chat, and is removed afterwards.  Records are kept in memory only
and capped so a long-running batch cannot grow without bound.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import time
from typing import TYPE_CHECKING, Any

from ..chat.manager import chat_manager
from ..util.error.types import SubAgentError
from .models import SubAgentRecord, SubAgentSpec, SubAgentStatus

if TYPE_CHECKING:
    from ..app import ProcooApp

logger = logging.getLogger("procoo_qt")

_ALLOWED_TOOL_MODES = frozenset(("allow", "block"))


class SubAgentManager:
    """Creates, runs, and tracks headless sub-agents.

    Attributes:
        records: In-memory records keyed by sub-agent id, oldest first.
    """

    def __init__(self, app: ProcooApp) -> None:
        """Initialise the manager.

        Args:
            app: The backend application holding config and skill subsystems.
        """
        self._app = app
        self.records: dict[str, SubAgentRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._prepared: dict[str, tuple[str, list[str], list[dict], dict[str, str]]] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self._counter = 0

    # ------------------------------------------------------------------
    #  Public: Create and run
    # ------------------------------------------------------------------

    def create(self, spec: SubAgentSpec) -> SubAgentRecord:
        """Validate a request, create its agent, and schedule the run.

        Args:
            spec: The sub-agent request.

        Returns:
            The queued record.

        Raises:
            SubAgentError: When the prompt, skills, model, or tools are invalid.
        """
        self._validate_spec(spec)
        model_name = self._resolve_model(spec)
        activated = self._dedupe(spec.activated_skills)
        self._validate_skills(activated)
        activated = self._strip_subagent_skill(activated)
        tool_defs, tool_config = self._resolve_tools(spec, activated)

        record_id = self._new_id()
        record = SubAgentRecord(
            id=record_id,
            status=SubAgentStatus.QUEUED,
            spec=spec,
            model_name=model_name,
            tool_config=tool_config,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._prepared[record_id] = (
            model_name,
            activated,
            tool_defs,
            tool_config,
        )
        self.records[record_id] = record
        self._tasks[record_id] = asyncio.ensure_future(self._execute(record))
        self._prune()
        logger.info(
            "Sub-agent '%s' queued (model=%s, tools=%d)",
            record_id,
            model_name,
            len(tool_config),
        )
        return record

    async def run(self, spec: SubAgentSpec) -> SubAgentRecord:
        """Create a sub-agent and wait for it to finish.

        Args:
            spec: The sub-agent request.

        Returns:
            The terminal record.
        """
        record = self.create(spec)
        await self.wait(record.id)
        return record

    async def wait(self, agent_id: str) -> SubAgentRecord | None:
        """Wait for a sub-agent task to finish.

        Args:
            agent_id: The sub-agent id.

        Returns:
            The terminal record, or ``None`` when the id is unknown.
        """
        record = self.records.get(agent_id)
        if record is None:
            return None
        task = self._tasks.get(agent_id)
        if task is not None and not task.done():
            with suppress(asyncio.CancelledError):
                await task
        return record

    async def cancel(self, agent_id: str) -> SubAgentRecord | None:
        """Cancel a running or queued sub-agent.

        Args:
            agent_id: The sub-agent id.

        Returns:
            The updated record, or ``None`` when the id is unknown.
        """
        record = self.records.get(agent_id)
        if record is None:
            return None
        if record.status.terminal:
            return record
        task = self._tasks.get(agent_id)
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        else:
            self._finish(record, SubAgentStatus.CANCELLED, error="Sub-agent cancelled.")
        return record

    # ------------------------------------------------------------------
    #  Public: Lookup
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> SubAgentRecord | None:
        """Return a record by id, or ``None``."""
        return self.records.get(agent_id)

    def list_records(self) -> list[SubAgentRecord]:
        """Return every in-memory record, oldest first."""
        return list(self.records.values())

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
        )

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Return the concurrency semaphore, creating it on first use."""
        if self._semaphore is None:
            limit = max(1, self._app.config.subagent_max_concurrent)
            self._semaphore = asyncio.Semaphore(limit)
        return self._semaphore

    async def _execute(self, record: SubAgentRecord) -> None:
        """Run one sub-agent under the concurrency limit and finalise its record.

        Args:
            record: The queued record to execute.
        """
        try:
            async with self._get_semaphore():
                prepared = self._prepared.get(record.id)
                if prepared is None:
                    self._finish(
                        record,
                        SubAgentStatus.ERROR,
                        error="Sub-agent preparation data was lost.",
                    )
                    return
                try:
                    self._build_chat(record.id, record.spec, *prepared)
                except Exception as error:
                    logger.error("Sub-agent '%s' could not start: %s", record.id, error)
                    self._finish(
                        record,
                        SubAgentStatus.ERROR,
                        error=f"Failed to create sub-agent: {error}",
                    )
                    return
                await self._run_record(record)
        except asyncio.CancelledError:
            self._finish(record, SubAgentStatus.CANCELLED, error="Sub-agent cancelled.")
            raise
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Sub-agent '%s' failed: %s", record.id, error)
            self._finish(record, SubAgentStatus.ERROR, error=str(error) or type(error).__name__)
        finally:
            self._prepared.pop(record.id, None)
            self._tasks.pop(record.id, None)
            chat_manager.remove_chat(record.id)

    async def _run_record(self, record: SubAgentRecord) -> None:
        """Drive the agent turn, apply the timeout, and store the result.

        Args:
            record: The record being executed.
        """
        record.status = SubAgentStatus.RUNNING
        agent = chat_manager.get_chat(record.id)
        if agent is None:
            self._finish(record, SubAgentStatus.ERROR, error="Sub-agent agent was not created.")
            return

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

        record.tokens = {
            "input": int(getattr(agent, "api_input_latest", 0) or 0),
            "output": int(getattr(agent, "api_output_sum", 0) or 0),
        }
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
            record: The record collecting tool-call summaries.

        Returns:
            The last error brief, or an empty string on success.
        """
        task = asyncio.ensure_future(agent.run(record.spec.prompt))
        error_message = ""
        try:
            while not task.done() or not agent.event_queue.empty():
                try:
                    event = await asyncio.wait_for(agent.event_queue.get(), timeout=0.1)
                except TimeoutError:
                    if not task.done():
                        continue
                    break
                error_message = self._handle_event(record, event, error_message)
            if not task.done():
                await task
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
            raise
        return error_message

    @staticmethod
    def _handle_event(record: SubAgentRecord, event: dict, error_message: str) -> str:
        """Record a tool call or error from the agent event stream.

        Args:
            record: The record collecting summaries.
            event: One agent event dict.
            error_message: The error brief accumulated so far.

        Returns:
            The updated error brief.
        """
        event_type = event.get("type", "")
        if event_type == "tool_call":
            record.tool_calls.append(
                {
                    "id": event.get("id", ""),
                    "name": event.get("name", ""),
                    "mode": event.get("mode", ""),
                    "arguments": event.get("arguments", {}),
                    "is_error": False,
                }
            )
        elif event_type == "tool_result":
            for call in reversed(record.tool_calls):
                if call.get("id") == event.get("id"):
                    call["is_error"] = bool(event.get("is_error"))
                    break
        elif event_type == "error":
            error_message = event.get("brief") or event.get("detail") or "Agent error"
        return error_message

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
        self._prune()
        logger.info("Sub-agent '%s' finished with %s", record.id, status)

    def _prune(self) -> None:
        """Drop the oldest terminal records above the configured cap."""
        limit = max(1, self._app.config.subagent_max_records)
        for agent_id in list(self.records):
            if len(self.records) <= limit:
                return
            if self.records[agent_id].status.terminal:
                del self.records[agent_id]

    def _new_id(self) -> str:
        """Return a unique sub-agent id."""
        self._counter += 1
        return f"subagent:{time.strftime('%Y%m%d_%H%M%S')}:{self._counter}"
