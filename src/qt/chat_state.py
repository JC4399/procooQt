"""Per-chat GUI state for the Procoo Qt UI.

Each live chat owns one :class:`ChatState` holding only the values the GUI
thread needs to render panels and tabs.  The ``Agent`` and the render pipeline
(including the item cache and the incremental Markdown renderers) live on the
chat's :class:`~src.qt.chat_worker.ChatWorker` thread, never here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatState:
    """Mutable GUI-visible state for a single chat.

    Attributes:
        chat_id: The chat this state belongs to.
        generation_id: Incremented per generation to detect stale turns.
        is_busy: Whether a generation is currently running.
        has_error: Whether the last generation errored or was stopped.
        is_loading: Whether a switch rebuild overlay is showing for this chat.
        pending_tool_info: The tool call awaiting approval.
        approval_text: Prompt shown in the approval bar.
        true_input_tokens: Latest true input token count from ``token_usage``.
        true_output_cum: Cumulative true output token count for the current run.
        message_count: Current message count reported by the worker.
        primary_count: Number of primary skills selected for this chat.
        allow_count: Number of tools set to ``allow``.
        ask_count: Number of tools set to ``ask``.
        block_count: Number of tools set to ``block``.
        model_name: LLM model selected for this chat (empty = config default).
    """

    chat_id: str
    generation_id: int = 0
    is_busy: bool = False
    has_error: bool = False
    is_loading: bool = False
    pending_tool_info: dict | None = None
    approval_text: str = ""
    true_input_tokens: int = 0
    true_output_cum: int = 0
    message_count: int = 0
    primary_count: int = 0
    allow_count: int = 0
    ask_count: int = 0
    block_count: int = 0
    model_name: str = ""

    def reset_turn(self) -> None:
        """Reset per-turn GUI state."""
        self.pending_tool_info = None
        self.approval_text = ""
