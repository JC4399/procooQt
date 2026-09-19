"""Global session manager that creates and tracks ``Agent`` instances."""

from __future__ import annotations

import logging

from .agent import Agent

logger = logging.getLogger("procoo_qt")


class SessionManager:
    """Factory and registry for ``Agent`` objects keyed by session ID.

    Attributes:
        sessions: Dictionary mapping session IDs to live ``Agent`` instances.
    """

    def __init__(self) -> None:
        self.sessions: dict[str, Agent] = {}

    async def create_session(
        self,
        session_id: str,
        model: dict | None = None,
        primary_skill_contents: list[dict] | None = None,
        secondary_skill_contents: list[dict] | None = None,
        tool_functions: list[dict] | None = None,
        tool_config: dict[str, str] | None = None,
        skills_dir: str = "",
        system_message: str = "You are a helpful assistant.",
        sampling_config: dict | None = None,
        initial_messages: list[dict] | None = None,
        summary_prompt: str = "",
        session_limits: dict | None = None,
    ) -> Agent:
        """Create (or replace) an ``Agent`` and register it.

        Args:
            session_id: Unique session identifier.
            model: LLM configuration dict (model_name, api_key, api_base).
            primary_skill_contents: List of skill-content dicts for primary skills.
            secondary_skill_contents: List of skill-content dicts for secondary skills.
            tool_functions: List of tool-definition dicts (name, script_path, …).
            tool_config: Per-tool mode mapping (``"allow"``, ``"ask"``, ``"block"``).
            skills_dir: Path to the skills directory.
            system_message: Base system prompt for the agent.
            sampling_config: Optional LLM sampling parameters.
            initial_messages: Optional list of role/content dicts to seed
                the conversation history and agent memory with.
            summary_prompt: Instruction used when summarizing an over-limit session.
            session_limits: Optional ``{"max_bytes": int, "max_tokens": int}``
                compaction limits.

        Returns:
            The newly created ``Agent``.
        """
        if session_id in self.sessions:
            self.remove_session(session_id)

        session = Agent(
            session_id=session_id,
            model=model or {},
            primary_skill_contents=primary_skill_contents or [],
            secondary_skill_contents=secondary_skill_contents or [],
            tool_functions=tool_functions or [],
            tool_config=tool_config or {},
            skills_dir=skills_dir,
            system_message=system_message,
            sampling_config=sampling_config,
            initial_messages=initial_messages,
            summary_prompt=summary_prompt,
            session_limits=session_limits,
        )
        self.sessions[session_id] = session
        return session

    # ------------------------------------------------------------------
    #  Public: Lookup
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> Agent | None:
        """Retrieve a live session by ID, or ``None`` if not found."""
        return self.sessions.get(session_id)

    def update_session_config(
        self,
        session_id: str,
        primary_skill_contents: list[dict],
        secondary_skill_contents: list[dict],
        tool_functions: list[dict],
        tool_config: dict[str, str],
    ) -> dict:
        """Push new skill/tool config to a live session.

        Returns the result dict from ``Agent.update_skill_config`` (with
        ``warnings``, ``added_primary``, etc.), or an empty result if no
        live session exists for *session_id*.
        """
        session = self.get_session(session_id)
        if session is None:
            return {"warnings": []}
        return session.update_skill_config(
            primary_skill_contents,
            secondary_skill_contents,
            tool_functions,
            tool_config,
        )

    # ------------------------------------------------------------------
    #  Public: Lifecycle
    # ------------------------------------------------------------------

    def remove_session(self, session_id: str) -> None:
        """Remove and discard a session without error if missing."""
        self.sessions.pop(session_id, None)

    async def cleanup_idle_sessions(self, max_idle_minutes: int = 30) -> None:
        """Placeholder for future idle-session cleanup logic.

        Args:
            max_idle_minutes: Maximum idle time before a session is eligible for cleanup.
        """
        pass


session_manager = SessionManager()
