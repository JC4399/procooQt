"""Per-session UI state for the Procoo Qt UI.

Each live session owns a :class:`SessionState` so several sessions can generate
concurrently while the user switches between them. The state holds model row indices
and small value objects, never QML objects.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamingCardState:
    """Tracking state for one streaming card (thinking or response).

    Attributes:
        item_index: Row index of the card in ``ChatListModel``, or ``None``.
        token_count: Last rendered token count for the card.
    """

    item_index: int | None = None
    token_count: int = 0

    def reset(self) -> None:
        """Clear the card tracking state."""
        self.item_index = None
        self.token_count = 0


@dataclass
class SessionState:
    """Mutable UI state for a single session.

    Attributes:
        session_id: The session this state belongs to.
        generation_id: Incremented per generation to detect stale tasks.
        is_busy: Whether a generation is currently running.
        active_task: The running ``Agent.run`` task, if any.
        approval_event: Set when the user resolves a pending tool approval.
        approval_text: Prompt shown in the approval bar.
        pending_tool_info: The tool call awaiting approval.
        current_tool_calls: Tool calls collected during the current turn.
        tool_results: Tool results collected during the current turn.
        thinking: Streaming state for the thinking card.
        response: Streaming state for the response card.
        context_banners_data: Delta context banners to render.
        init_banner_displayed: Whether the initial context banner was shown.
        true_input_tokens: Latest true input token count from ``token_usage``.
        true_output_cum: Cumulative true output token count.
        rendered_item_keys: Content hashes of the last rendered chat items.
        tool_call_indices: Row indices of rendered tool-call cards.
        last_rendered_thinking_text: Last thinking text pushed to the model.
        last_rendered_message_text: Last response text pushed to the model.
        last_rendered_tool_calls: Last rendered tool-call count.
        last_rendered_tool_results: Last rendered tool-result count.
        last_rendered_streaming_tc_json: Last rendered streaming tool-call JSON.
        last_tok_counted_thinking: Thinking prefix already counted for tokens.
        last_tok_counted_response: Response prefix already counted for tokens.
        last_content_update_time: Monotonic time of the last content-only update.
        last_rebuild_time: Monotonic time of the last structural rebuild.
    """

    session_id: str
    generation_id: int = 0
    is_busy: bool = False
    active_task: asyncio.Task[Any] | None = None
    approval_event: asyncio.Event | None = None
    approval_text: str = ""
    pending_tool_info: dict[str, Any] | None = None
    current_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    thinking: StreamingCardState = field(default_factory=StreamingCardState)
    response: StreamingCardState = field(default_factory=StreamingCardState)
    context_banners_data: list[dict[str, Any]] = field(default_factory=list)
    init_banner_displayed: bool = False
    true_input_tokens: int = 0
    true_output_cum: int = 0
    rendered_item_keys: list[str] = field(default_factory=list)
    tool_call_indices: list[int] = field(default_factory=list)
    last_rendered_thinking_text: str = ""
    last_rendered_message_text: str = ""
    last_rendered_tool_calls: int = 0
    last_rendered_tool_results: int = 0
    last_rendered_streaming_tc_json: str = ""
    last_tok_counted_thinking: str = ""
    last_tok_counted_response: str = ""
    last_content_update_time: float = 0.0
    last_rebuild_time: float = 0.0

    def reset_turn(self) -> None:
        """Reset per-turn streaming and render-tracking state."""
        self.thinking.reset()
        self.response.reset()
        self.current_tool_calls.clear()
        self.tool_results.clear()
        self.pending_tool_info = None
        self.approval_event = None
        self.approval_text = ""
        self.true_input_tokens = 0
        self.true_output_cum = 0
        self.rendered_item_keys.clear()
        self.tool_call_indices.clear()
        self.last_rendered_thinking_text = ""
        self.last_rendered_message_text = ""
        self.last_rendered_tool_calls = 0
        self.last_rendered_tool_results = 0
        self.last_rendered_streaming_tc_json = ""
        self.last_tok_counted_thinking = ""
        self.last_tok_counted_response = ""
        self.last_content_update_time = 0.0
        self.last_rebuild_time = 0.0
