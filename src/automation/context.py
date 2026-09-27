"""Automation execution context bridging scripts to the in-app agent loop.

An ``AUTOMATION.py`` receives an :class:`AutomationContext` as the single argument
of its ``async def run(ctx)`` function.  The context lets a script ask the LLM
using the same ReAct agent the chat UI uses, without opening a chat panel, and
collect a human-readable run log.  It also exposes the triggering event payload
for event-driven automations.

Scripts run on the single qasync event loop, so they must never block it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from ..chat.manager import chat_manager
from ..util.error.types import AutomationError

if TYPE_CHECKING:
    from ..config.manager import ConfigManager
    from ..skill.manager import SkillManager
    from .models import AutomationInfo

logger = logging.getLogger("procoo_qt")


class AutomationContext:
    """Runtime context handed to an automation's ``run(ctx)`` function.

    Attributes:
        automation: The automation being executed.
        payload: Parsed JSON body from the triggering event (empty for schedules).
    """

    def __init__(
        self,
        automation: AutomationInfo,
        config: ConfigManager,
        skill_manager: SkillManager,
        skills_dir: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Initialise the context.

        Args:
            automation: The automation metadata (skills, path, name).
            config: The application config (LLM selection, prompts).
            skill_manager: Loads skill contents/tools for the automation's agent.
            skills_dir: Path to the skills directory.
            payload: Optional event payload passed to event-driven automations.
        """
        self.automation = automation
        self.payload: dict[str, Any] = dict(payload or {})
        self._config = config
        self._skill_manager = skill_manager
        self._skills_dir = skills_dir
        self._log_lines: list[str] = []

    # ------------------------------------------------------------------
    #  Public: Logging
    # ------------------------------------------------------------------

    def log(self, message: str) -> None:
        """Append a line to the automation's run log.

        Args:
            message: The log line to record.
        """
        self._log_lines.append(str(message))

    @property
    def log_text(self) -> str:
        """Return the accumulated script log lines joined by newlines."""
        return "\n".join(self._log_lines)

    # ------------------------------------------------------------------
    #  Public: LLM access
    # ------------------------------------------------------------------

    async def ask(self, prompt: str) -> str:
        """Run one headless agent turn and return the assistant reply.

        A temporary chat is created from the automation's configured skills,
        its event queue is drained, and the chat is removed afterwards.  All
        tools are forced to ``allow`` because no user is available to approve
        them (automations are authored deliberately).

        Args:
            prompt: The user message to send to the agent.

        Returns:
            The final assistant message text.

        Raises:
            AutomationError: If the agent reports an error or returns no text.
        """
        chat_id = f"automation:{self.automation.path}:{time.strftime('%Y%m%d_%H%M%S')}"
        primary = self.automation.primary_skills
        secondary = self.automation.secondary_skills
        tool_defs = self._skill_manager.load_tool_functions(primary)
        agent = chat_manager.create_chat(
            chat_id=chat_id,
            model=self._config.llm_config(self._config.llm_model_name),
            primary_skill_contents=self._skill_manager.load_skill_contents(primary),
            secondary_skill_contents=self._skill_manager.load_skill_contents(secondary),
            tool_functions=tool_defs,
            tool_config={td["name"]: "allow" for td in tool_defs},
            skills_dir=self._skills_dir,
            system_message=self._config.agent_system_prompt,
            summary_prompt=self._config.agent_summary_prompt,
            chat_limits={"max_bytes": 0, "max_tokens": 0},
        )
        self.log(f"[agent] ask: {prompt}")
        try:
            text = await self._consume_agent(agent, prompt)
        finally:
            chat_manager.remove_chat(chat_id)
        return text

    # ------------------------------------------------------------------
    #  Private: Event consumption
    # ------------------------------------------------------------------

    async def _consume_agent(self, agent: Any, prompt: str) -> str:
        """Run the agent turn and drain its event queue.

        Args:
            agent: The live headless ``Agent``.
            prompt: The user message to send.

        Returns:
            The final assistant message text.

        Raises:
            AutomationError: When the agent emits an error or produces no text.
        """
        task = asyncio.ensure_future(agent.run(prompt))
        error_message = ""
        try:
            while not task.done() or not agent.event_queue.empty():
                try:
                    event = await asyncio.wait_for(agent.event_queue.get(), timeout=0.1)
                except TimeoutError:
                    if not task.done():
                        continue
                    break
                error_message = self._log_event(event, error_message)
            if not task.done():
                await task
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
            raise

        if error_message:
            raise AutomationError(brief=error_message, detail=error_message)

        text = self._last_assistant_text(agent)
        if not text:
            raise AutomationError(
                brief="Automation agent returned no response.",
                detail="Headless agent finished without an assistant message.",
            )
        return text

    def _log_event(self, event: dict, error_message: str) -> str:
        """Record an agent event in the run log and return any error brief.

        Args:
            event: The agent event dict.
            error_message: The error brief accumulated so far.

        Returns:
            The updated error brief.
        """
        etype = event.get("type", "")
        if etype == "tool_call":
            self.log(f"[agent] tool_call {event.get('name', '')} ({event.get('mode', '')})")
        elif etype == "tool_result":
            self.log(f"[agent] tool_result {event.get('name', '')}")
        elif etype == "error":
            error_message = event.get("brief") or event.get("detail") or "Agent error"
        return error_message

    @staticmethod
    def _last_assistant_text(agent: Any) -> str:
        """Return the last non-empty assistant message content.

        Args:
            agent: The live headless ``Agent``.

        Returns:
            The assistant text, or an empty string.
        """
        for message in reversed(agent.messages):
            if message.get("role") != "assistant":
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return ""
