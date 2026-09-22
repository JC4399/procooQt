"""Global chat manager that creates and tracks ``Agent`` instances."""

from __future__ import annotations

import logging

from .agent import Agent

logger = logging.getLogger("procoo_qt")


class ChatManager:
    """Factory and registry for ``Agent`` objects keyed by chat ID.

    Attributes:
        chats: Dictionary mapping chat IDs to live ``Agent`` instances.
    """

    def __init__(self) -> None:
        self.chats: dict[str, Agent] = {}

    def create_chat(
        self,
        chat_id: str,
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
        chat_limits: dict | None = None,
    ) -> Agent:
        """Create (or replace) an ``Agent`` and register it.

        Args:
            chat_id: Unique chat identifier.
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
            summary_prompt: Instruction used when summarizing an over-limit chat.
            chat_limits: Optional ``{"max_bytes": int, "max_tokens": int}``
                compaction limits.

        Returns:
            The newly created ``Agent``.
        """
        if chat_id in self.chats:
            self.remove_chat(chat_id)

        chat = Agent(
            chat_id=chat_id,
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
            chat_limits=chat_limits,
        )
        self.chats[chat_id] = chat
        return chat

    # ------------------------------------------------------------------
    #  Public: Lookup
    # ------------------------------------------------------------------

    def get_chat(self, chat_id: str) -> Agent | None:
        """Retrieve a live chat by ID, or ``None`` if not found."""
        return self.chats.get(chat_id)

    def update_chat_config(
        self,
        chat_id: str,
        primary_skill_contents: list[dict],
        secondary_skill_contents: list[dict],
        tool_functions: list[dict],
        tool_config: dict[str, str],
    ) -> dict:
        """Push new skill/tool config to a live chat.

        Returns the result dict from ``Agent.update_skill_config`` (with
        ``warnings``, ``added_primary``, etc.), or an empty result if no
        live chat exists for *chat_id*.
        """
        chat = self.get_chat(chat_id)
        if chat is None:
            return {"warnings": []}
        return chat.update_skill_config(
            primary_skill_contents,
            secondary_skill_contents,
            tool_functions,
            tool_config,
        )

    # ------------------------------------------------------------------
    #  Public: Lifecycle
    # ------------------------------------------------------------------

    def remove_chat(self, chat_id: str) -> None:
        """Remove and discard a chat without error if missing."""
        self.chats.pop(chat_id, None)

    async def cleanup_idle_chats(self, max_idle_minutes: int = 30) -> None:
        """Placeholder for future idle-chat cleanup logic.

        Args:
            max_idle_minutes: Maximum idle time before a chat is eligible for cleanup.
        """
        pass


chat_manager = ChatManager()
