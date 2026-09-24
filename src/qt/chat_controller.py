"""``ChatController`` — chat rendering, streaming, approval, and token bar.

Owns one :class:`ChatListModel` per live chat and drives the ReAct event loop. It
handles both build/render and events/streaming. ``chat.messages`` stays canonical:
the render plan is derived from it, diffed by content hash, and clipped into the model.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass, field
import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..chat.manager import chat_manager
from ..util.tokens.counter import count_tokens
from .chat_items import (
    _parse_tool_arguments,
    build_response_item,
    build_response_pending_item,
    build_thinking_item,
    build_thinking_pending_item,
    build_tool_call_item,
    build_tool_call_pending_item,
    build_tool_result_item,
    build_tool_result_pending_item,
    build_user_item,
    build_waiting_item,
)
from .context_banner import build_context_banner_item, build_context_sections_from_snapshot
from .error_handler import TOAST_ERROR
from .markdown import render_markdown
from .models.chat_list_model import ChatListModel
from .qt_roles import ChatRole

if TYPE_CHECKING:
    from ..app import ProcooApp
    from ..chat.agent import Agent
    from .chat_state import ChatState
    from .session_controller import SessionController

logger = logging.getLogger("procoo_qt")

#: Minimum seconds between in-place streaming body updates for thinking/response
#: cards. Structural changes rebuild immediately; this only paces text re-renders
#: of the accumulated markdown so long outputs do not thrash the rich-text layout.
_STREAM_UPDATE_INTERVAL = 0.08

#: Staged chat build after a chat switch. The chat list is non-virtualized, so
#: inserting every card at once blocks the GUI thread for the whole build; rows
#: are inserted ``_RENDER_INSERT_BATCH`` at a time with a short tick so the
#: loading overlay's scanner keeps animating. The tick bounds the extra time the
#: staging adds to roughly ``_RENDER_TICK_TARGET`` seconds.
_RENDER_INSERT_BATCH = 8
_RENDER_TICK_MIN = 0.006
_RENDER_TICK_MAX = 0.02
_RENDER_TICK_TARGET = 0.6


@dataclass
class _StagedBuildState:
    """Tracks an in-progress staged chat build after a chat switch.

    Attributes:
        chat_id: The chat whose cards are being built.
        model: The chat model receiving rows.
        state: The chat state that owns the render keys.
        items: The full render plan (role-keyed rows).
        keys: Identity keys aligned with ``items``.
        next_index: The next row index to insert.
        done: Whether the build finished or was skipped.
    """

    chat_id: str
    model: ChatListModel
    state: ChatState
    items: list[dict]
    keys: list[str]
    next_index: int = 0
    done: bool = False


@dataclass
class _RenderIndices:
    """Row indices of the streaming-capable cards produced by a render plan.

    Returned by :meth:`ChatController._build_items` instead of mutating the
    chat state, so the plan can be computed on a worker thread and the
    indices applied on the GUI thread.

    Attributes:
        thinking_index: Row index of the pending thinking card, or ``None``.
        response_index: Row index of the pending response card, or ``None``.
        tool_call_indices: Row indices of the streaming tool-call cards.
    """

    thinking_index: int | None = None
    response_index: int | None = None
    tool_call_indices: list[int] = field(default_factory=list)


# ------------------------------------------------------------------
#  Module-level content helpers
# ------------------------------------------------------------------


def _content_hash(data: str | list) -> str:
    """Return a short stable content hash for render planning.

    Args:
        data: A string or a JSON-serializable list.

    Returns:
        A 16-character blake2b hex digest.
    """
    if isinstance(data, list):
        data = json.dumps(data, sort_keys=True)
    return hashlib.blake2b(data.encode()).hexdigest()[:16]


def _extract_text_from_multimodal(content_parts: list) -> str:
    """Extract text parts from a multimodal content list for display.

    Args:
        content_parts: Content part dicts (``{"type": "text", ...}`` or
            ``{"type": "image_url", ...}``).

    Returns:
        Joined text parts, or ``"[IMAGE]"`` if there are no text parts.
    """
    texts: list[str] = []
    for part in content_parts:
        if isinstance(part, dict) and part.get("type") == "text":
            texts.append(part.get("text", ""))
    return "\n".join(texts) if texts else "[IMAGE]"


def normalize_content(content: str | list) -> str:
    """Normalise message content to a string for hashing and display.

    Args:
        content: Either a string or a multimodal content list.

    Returns:
        String representation of the content.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _extract_text_from_multimodal(content)
    return str(content)


def _assistant_decision(msg: dict) -> dict[str, Any]:
    """Extract common decision state from an assistant message.

    Centralises whether thinking/response cards are "done" (a later card type
    exists on the same message) and which tool calls are finalised. Used by both
    key computation and item building.

    Args:
        msg: The assistant message dict.

    Returns:
        Dict with thinking/response text, tool-call lists, done flags, and
        ``finalized_ids``.
    """
    thinking_text = msg.get("reasoning_content", "")
    content_text = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls", [])
    streaming_tcs = msg.get("_streaming_tool_calls", [])
    return {
        "thinking_text": thinking_text,
        "content_text": content_text,
        "tool_calls": tool_calls,
        "streaming_tcs": streaming_tcs,
        "effective_tool_calls": streaming_tcs or tool_calls,
        "thinking_done": bool(content_text) or bool(tool_calls),
        "response_done": bool(tool_calls),
        "finalized_ids": {tc.get("id", "") for tc in tool_calls},
    }


def _is_waiting_for_assistant(state: ChatState, messages: list[dict]) -> bool:
    """Return whether the UI should show the pre-response waiting scanner.

    Args:
        state: The chat's UI state.
        messages: The chat's message list.

    Returns:
        ``True`` while a generation is busy but the current assistant turn has
        not yet produced thinking, response, or tool-call content.
    """
    if not state.is_busy or not messages:
        return False
    last = messages[-1]
    if last.get("role") != "assistant":
        return True
    decision = _assistant_decision(last)
    return not (
        decision["thinking_text"] or decision["content_text"] or decision["effective_tool_calls"]
    )


def _count_trailing_tool_results(messages: list[dict], after_idx: int) -> int:
    """Count consecutive tool-result messages after *after_idx*.

    Args:
        messages: The full message list.
        after_idx: The index to start counting after.

    Returns:
        The number of leading ``role == "tool"`` messages.
    """
    count = 0
    for j in range(after_idx + 1, len(messages)):
        if messages[j].get("role") == "tool":
            count += 1
        else:
            break
    return count


def _compute_assistant_keys(
    msg: dict, messages: list[dict], idx: int, is_last_busy: bool
) -> list[str]:
    """Compute render keys for one assistant message.

    Args:
        msg: The assistant message dict.
        messages: Full message list (for looking ahead at tool results).
        idx: Current message index.
        is_last_busy: Whether this is the last message and the chat is busy.

    Returns:
        List of render-plan key strings for this assistant message.
    """
    keys: list[str] = []
    d = _assistant_decision(msg)

    if is_last_busy:
        if d["thinking_text"]:
            if d["thinking_done"]:
                keys.append("t:" + _content_hash(d["thinking_text"]) + ":done")
            else:
                keys.append("t:pending")
        if d["content_text"]:
            if d["response_done"]:
                keys.append("r:" + _content_hash(d["content_text"]) + ":done")
            else:
                keys.append("r:pending")
        for tc in d["effective_tool_calls"]:
            tc_id = tc.get("id", "")
            name = tc.get("function", {}).get("name", "")
            if tc_id in d["finalized_ids"]:
                args = tc.get("function", {}).get("arguments", "{}")
                keys.append("c:" + name + ":" + _content_hash(args) + ":f")
            else:
                keys.append("c:p:" + name + ":" + tc_id)
        if d["tool_calls"]:
            result_count = _count_trailing_tool_results(messages, idx)
            for k in range(result_count, len(d["tool_calls"])):
                tc = d["tool_calls"][k]
                keys.append(
                    "ptr:" + tc.get("function", {}).get("name", "") + ":" + tc.get("id", "")
                )
        return keys

    if d["thinking_text"]:
        keys.append("t:" + _content_hash(d["thinking_text"]))
    if d["content_text"]:
        keys.append("r:" + _content_hash(d["content_text"]))
    for tc in d["effective_tool_calls"]:
        name = tc.get("function", {}).get("name", "")
        args = tc.get("function", {}).get("arguments", "{}")
        tc_id = tc.get("id", "")
        keys.append("c:" + name + ":" + _content_hash(args) + ":" + tc_id)
    return keys


def _accumulate_tokens(text: str, previous: str, current: int) -> int:
    """Accumulate a token estimate for streamed text.

    Args:
        text: The full current text.
        previous: The previously counted prefix.
        current: The previous accumulated token count.

    Returns:
        The updated token count.
    """
    old_len = len(previous)
    if old_len <= len(text):
        return current + count_tokens(text[old_len:])
    return count_tokens(text)


class ChatController(QObject):
    """Chat list rendering, streaming, approval, and token-accounting controller."""

    active_model_changed = Signal()
    approval_visibility_changed = Signal(bool)
    token_counts_changed = Signal(int, int)
    toast_requested = Signal(str, str)
    busy_changed = Signal(bool)
    loading_changed = Signal(bool)
    chat_state_changed = Signal(str)

    if TYPE_CHECKING:
        # Attributes provided by ui.py orchestrator
        app: ProcooApp
        session: SessionController

        # Attributes owned by this controller
        _models: dict[str, ChatListModel]
        _tasks: set[asyncio.Task[Any]]
        _visible_chat_ids: set[str]
        active_chat_id: str | None
        _approval_visible: bool
        _approval_text: str
        _busy: bool
        _loading: bool
        _input_tokens: int
        _output_tokens: int
        _staged_build: _StagedBuildState | None

        # Cross-controller method stubs
        def _refresh_sidebar(self) -> None: ...
        def set_visible_chats(self, chat_ids: set[str]) -> None: ...

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the chat controller.

        Args:
            app: The top-level application holding backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._models = {}
        self._tasks = set()
        self._visible_chat_ids = set()
        self.active_chat_id = None
        self._approval_visible = False
        self._approval_text = ""
        self._busy = False
        self._loading = False
        self._input_tokens = 0
        self._output_tokens = 0
        self._staged_build = None

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the per-chat chat models."""
        self._models = {}
        self._visible_chat_ids = set()
        self.active_chat_id = None

    # ------------------------------------------------------------------
    #  Public: visible panels
    # ------------------------------------------------------------------

    def set_visible_chats(self, chat_ids: set[str]) -> None:
        """Record which chats are currently shown in a panel.

        Event rendering is gated on this set so streaming is only painted for
        chats that are on screen.

        Args:
            chat_ids: The active chat id of every visible panel.
        """
        self._visible_chat_ids = set(chat_ids)

    def _is_visible(self, chat_id: str) -> bool:
        """Return whether a chat is currently shown in a panel.

        Args:
            chat_id: The chat id to test.

        Returns:
            ``True`` if the chat is visible.
        """
        return chat_id in self._visible_chat_ids

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=active_model_changed)
    def activeModel(self) -> ChatListModel | None:  # noqa: N802
        """Return the chat model for the active chat.

        Returns:
            The active chat's chat model, or ``None``.
        """
        if self.active_chat_id is None:
            return None
        return self._models.get(self.active_chat_id)

    @Property(bool, notify=approval_visibility_changed)
    def approvalVisible(self) -> bool:  # noqa: N802
        """Return whether the approval bar is shown.

        Returns:
            ``True`` while a tool call awaits approval.
        """
        return self._approval_visible

    @Property(str, notify=approval_visibility_changed)
    def approvalText(self) -> str:  # noqa: N802
        """Return the approval prompt text.

        Returns:
            The current approval prompt, or an empty string.
        """
        return self._approval_text

    @Property(bool, notify=busy_changed)
    def busy(self) -> bool:
        """Return whether the active chat is generating.

        Returns:
            ``True`` while a generation is running.
        """
        return self._busy

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        """Return whether a chat switch rebuild is in progress.

        Returns:
            ``True`` while the chat display is rebuilding after a switch.
        """
        return self._loading

    @Property(int, notify=token_counts_changed)
    def inputTokens(self) -> int:  # noqa: N802
        """Return the active chat's context (input) token count.

        Returns:
            True input tokens when known, otherwise the estimate.
        """
        return self._input_tokens

    @Property(int, notify=token_counts_changed)
    def outputTokens(self) -> int:  # noqa: N802
        """Return the active chat's cumulative output token count.

        Returns:
            Cumulative output tokens for the chat.
        """
        return self._output_tokens

    # ------------------------------------------------------------------
    #  State
    # ------------------------------------------------------------------

    def model_for(self, chat_id: str) -> ChatListModel:
        """Return the chat model for a chat, creating it on demand.

        Args:
            chat_id: The chat id.

        Returns:
            The chat's chat model.
        """
        if chat_id not in self._models:
            self._models[chat_id] = ChatListModel(self)
        return self._models[chat_id]

    def _refresh_sidebar(self) -> None:
        """Refresh the chat sidebar so status dots and counts update."""
        self.session._refresh_model()

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Schedule a coroutine and keep a reference until it completes.

        Args:
            coro: The coroutine to schedule on the running event loop.
        """
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # ------------------------------------------------------------------
    #  Slot: Send
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_send(self, text: str) -> None:
        """Validate a message and send it to the focused chat.

        Args:
            text: The user message text typed into the input.
        """
        self._handle_send_for(self.active_chat_id or "", text)

    @Slot(str, str)
    def _handle_send_for(self, chat_id: str, text: str) -> None:
        """Validate a message and launch generation for a chat.

        Args:
            chat_id: The chat to send the message to.
            text: The user message text typed into the input.
        """
        message = text or ""
        if not message.strip():
            self.toast_requested.emit("Please enter a message.", TOAST_ERROR)
            return
        if not chat_id:
            self.toast_requested.emit("Please create or select a chat first.", TOAST_ERROR)
            return
        state = self.session.state(chat_id)
        if state.is_busy:
            self.toast_requested.emit("Please wait for the current response.", TOAST_ERROR)
            return
        self._skip_staged_build()
        self._append_user_message(chat_id, message)
        self._launch_generation(chat_id, message)

    # ------------------------------------------------------------------
    #  Slot: Stop / Regenerate / Approve / Deny
    # ------------------------------------------------------------------

    @Slot()
    def _handle_stop(self) -> None:
        """Stop the focused chat's generation."""
        self._spawn(self._stop_generation(self.active_chat_id or ""))

    @Slot(str)
    def _handle_stop_for(self, chat_id: str) -> None:
        """Stop a specific chat's generation.

        Args:
            chat_id: The chat to stop.
        """
        self._spawn(self._stop_generation(chat_id))

    @Slot()
    def _handle_regenerate(self) -> None:
        """Regenerate the last user message in the focused chat."""
        self._spawn(self._regenerate(self.active_chat_id or ""))

    @Slot(str)
    def _handle_regenerate_for(self, chat_id: str) -> None:
        """Regenerate the last user message in a specific chat.

        Args:
            chat_id: The chat to regenerate.
        """
        self._spawn(self._regenerate(chat_id))

    @Slot()
    def _handle_approve(self) -> None:
        """Approve the focused chat's pending tool call."""
        self._spawn(self._approve(self.active_chat_id or ""))

    @Slot(str)
    def _handle_approve_for(self, chat_id: str) -> None:
        """Approve a specific chat's pending tool call.

        Args:
            chat_id: The chat whose tool call to approve.
        """
        self._spawn(self._approve(chat_id))

    @Slot(str)
    def _handle_deny(self, reason: str) -> None:
        """Deny the focused chat's pending tool call.

        Args:
            reason: Optional denial reason typed by the user.
        """
        self._spawn(self._deny(self.active_chat_id or "", reason))

    @Slot(str, str)
    def _handle_deny_for(self, chat_id: str, reason: str) -> None:
        """Deny a specific chat's pending tool call.

        Args:
            chat_id: The chat whose tool call to deny.
            reason: Optional denial reason typed by the user.
        """
        self._spawn(self._deny(chat_id, reason))

    # ------------------------------------------------------------------
    #  Slot: Chat activated
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_chat_switch_started(self, chat_id: str) -> None:
        """Show the loading scanner as soon as a chat switch is requested.

        Args:
            chat_id: The chat being switched to.
        """
        if not chat_id:
            return
        self._cancel_staged_build()
        self._set_loading(chat_id, True)

    @Slot(str)
    def _handle_chat_activated(self, chat_id: str) -> None:
        """Focus a chat and rebuild its display.

        Args:
            chat_id: The newly activated chat id (empty when none).
        """
        self._cancel_staged_build()
        self.active_chat_id = chat_id or None
        if not chat_id:
            self._set_approval_visible(False)
            self.active_model_changed.emit()
            return
        self.model_for(chat_id)
        state = self.session.state(chat_id)
        state.rendered_item_keys = []
        state.tool_call_indices.clear()
        self.active_model_changed.emit()
        self._set_loading(chat_id, True)
        self._spawn(self._rebuild_after_switch(chat_id))

    async def _rebuild_after_switch(self, chat_id: str) -> None:
        """Rebuild a chat's display after it becomes visible.

        Args:
            chat_id: The chat that was activated.
        """
        await asyncio.sleep(0)
        if not self._is_visible(chat_id):
            return
        await self._rebuild_chat_display_staged(chat_id)
        if not self._is_visible(chat_id):
            return
        self._set_loading(chat_id, False)
        self.chat_state_changed.emit(chat_id)

    # ------------------------------------------------------------------
    #  Generation lifecycle
    # ------------------------------------------------------------------

    def _launch_generation(self, chat_id: str, message: str) -> None:
        """Mark a chat busy and schedule the streaming chat loop.

        Args:
            chat_id: The chat to generate for.
            message: User message text to send.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        state.is_busy = True
        state.generation_id += 1
        gen_id = state.generation_id
        self._append_waiting_placeholder(chat_id)
        self._refresh_sidebar()
        self.chat_state_changed.emit(chat_id)
        self._spawn(self._run_chat_loop(message, gen_id, chat_id))

    async def _run_chat_loop(self, message: str, gen_id: int, chat_id: str) -> None:
        """Stream one turn: hydrate, consume events, then clean up.

        Args:
            message: User message text to send.
            gen_id: Generation counter for stale-task detection.
            chat_id: The chat to run against.
        """
        state = self.session.state(chat_id)
        chat = await self._hydrate_phase(chat_id, gen_id)
        if chat is None:
            return
        task = asyncio.ensure_future(chat.run(message))
        state.active_task = task
        await asyncio.sleep(0)
        if self._is_visible(chat_id):
            self._rebuild_chat_display(chat_id)
        try:
            await self._consume_events(chat, chat_id, state, task)
            if not task.done():
                await task
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
        finally:
            self._finalize_turn(chat_id, state, gen_id)
        if chat.check_limit_exceeded() is not None:
            await self._compact_chat(chat_id, chat)

    async def _hydrate_phase(self, chat_id: str, gen_id: int) -> Agent | None:
        """Hydrate the live chat, cleaning up on failure.

        Args:
            chat_id: The chat to hydrate.
            gen_id: Generation counter for stale-task detection.

        Returns:
            The live chat, or ``None`` when hydration failed.
        """
        state = self.session.state(chat_id)
        chat = await self.session._hydrate_chat(chat_id)
        if chat is not None:
            return chat
        if state.generation_id == gen_id:
            state.is_busy = False
            if self._is_visible(chat_id):
                self._rebuild_chat_display(chat_id)
            self.chat_state_changed.emit(chat_id)
            self._refresh_sidebar()
        return None

    async def _consume_events(
        self, chat: Agent, chat_id: str, state: ChatState, task: asyncio.Task[Any]
    ) -> None:
        """Drain the chat event queue until the turn task finishes.

        Args:
            chat: The live agent chat.
            chat_id: The chat id being rendered.
            state: The chat's UI state.
            task: The running ``Agent.run`` task.
        """
        last_count = 0
        last_rendered = 0
        while not task.done() or not chat.event_queue.empty():
            try:
                event = await asyncio.wait_for(chat.event_queue.get(), timeout=0.1)
            except TimeoutError:
                if not task.done():
                    continue
                break
            etype = event.get("type", "")
            if etype == "tool_call" and event.get("mode", "ask") == "ask":
                await self._handle_approval(chat_id, event, state)
            elif etype == "tool_result":
                state.tool_results.append(event)
            elif etype == "token_usage":
                state.true_input_tokens = event.get("input", 0)
                state.true_output_cum = event.get("output_cumulative", 0)
                if self._is_visible(chat_id):
                    self._update_token_bar(chat_id, state)
            elif etype == "done":
                break
            elif etype == "error":
                brief = event.get("brief", event.get("message", "Unknown error"))
                if self._is_visible(chat_id):
                    self.toast_requested.emit(brief, TOAST_ERROR)
                break

            msg_count = len(chat.messages)
            if msg_count != last_count:
                last_count = msg_count
                self._refresh_sidebar()
            if self._is_visible(chat_id):
                last_rendered = self._render_active_event(
                    event, chat, chat_id, state, msg_count, last_rendered
                )

    def _render_active_event(
        self,
        event: dict,
        chat: Agent,
        chat_id: str,
        state: ChatState,
        msg_count: int,
        last_rendered: int,
    ) -> int:
        """Render the active chat after one event.

        Args:
            event: The event just consumed.
            chat: The live agent chat.
            chat_id: The active chat id.
            state: The chat's UI state.
            msg_count: Current message count.
            last_rendered: Message count at the last render.

        Returns:
            The updated last-rendered message count.
        """
        if msg_count != last_rendered:
            if event.get("type", "") == "tool_result":
                self._swap_pending_result_card(
                    chat_id, event.get("id", ""), event.get("name", ""), event.get("content", "")
                )
            else:
                self._rebuild_chat_display(chat_id)
            return msg_count
        if chat.messages and chat.messages[-1].get("role") != "assistant":
            self._rebuild_chat_display(chat_id)
        else:
            self._update_live_assistant(chat_id, state)
        return last_rendered

    def _finalize_turn(self, chat_id: str, state: ChatState, gen_id: int) -> None:
        """Clear busy state, persist the chat, and reset per-turn tracking.

        Args:
            chat_id: The chat that finished.
            state: The chat's UI state.
            gen_id: Generation counter for stale-task detection.
        """
        if state.generation_id == gen_id:
            state.is_busy = False
        if self._is_visible(chat_id):
            self._rebuild_chat_display(chat_id)
        if state.generation_id == gen_id:
            state.active_task = None
            state.reset_turn()
            self.session._save_current_chat_for(chat_id)
            self._refresh_sidebar()
            if self._is_visible(chat_id):
                self.chat_state_changed.emit(chat_id)

    # ------------------------------------------------------------------
    #  Stop / regenerate / approve / deny
    # ------------------------------------------------------------------

    async def _stop_generation(self, chat_id: str) -> None:
        """Deny any pending tool, release approval, and cancel the task.

        Args:
            chat_id: The chat to stop.
        """
        self._skip_staged_build()
        if not chat_id:
            return
        state = self.session.state(chat_id)
        if state.pending_tool_info:
            chat = chat_manager.get_chat(chat_id)
            if chat:
                await chat.deny_tool(state.pending_tool_info.get("id", ""))
        if state.approval_event and not state.approval_event.is_set():
            state.approval_event.set()
        if state.active_task and not state.active_task.done():
            state.active_task.cancel()
        self._set_approval_visible(False)
        self.chat_state_changed.emit(chat_id)
        logger.info("Generation stopped by user in chat '%s'", chat_id)

    async def _approve(self, chat_id: str) -> None:
        """Approve the pending tool call and release the blocked loop.

        Args:
            chat_id: The chat whose tool call to approve.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        if not state.pending_tool_info:
            return
        chat = chat_manager.get_chat(chat_id)
        if chat:
            await chat.approve_tool(state.pending_tool_info.get("id", ""))
        if state.approval_event:
            state.approval_event.set()
        self.chat_state_changed.emit(chat_id)

    async def _deny(self, chat_id: str, reason: str) -> None:
        """Deny the pending tool call and release the blocked loop.

        Args:
            chat_id: The chat whose tool call to deny.
            reason: Optional denial reason text.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        if not state.pending_tool_info:
            return
        chat = chat_manager.get_chat(chat_id)
        if chat:
            await chat.deny_tool(
                state.pending_tool_info.get("id", ""), denial_reason=(reason or "").strip()
            )
        if state.approval_event:
            state.approval_event.set()
        self.chat_state_changed.emit(chat_id)

    async def _regenerate(self, chat_id: str) -> None:
        """Trim the last turn and re-send the last user message.

        Args:
            chat_id: The chat to regenerate.
        """
        if not chat_id:
            self.toast_requested.emit("Please create or select a chat first.", TOAST_ERROR)
            return
        state = self.session.state(chat_id)
        if state.is_busy:
            self.toast_requested.emit("Please wait for the current response.", TOAST_ERROR)
            return
        last_user_msg = self._find_last_user_message(chat_id)
        if not last_user_msg:
            self.toast_requested.emit("No message to regenerate.", TOAST_ERROR)
            return
        self._trim_stored_chat(chat_id)
        state.context_banners_data = [
            banner for banner in state.context_banners_data if not banner.get("is_delta")
        ]
        chat_manager.remove_chat(chat_id)
        logger.info("Regenerating last message in chat '%s'", chat_id)
        self._rebuild_chat_display(chat_id)
        self._launch_generation(chat_id, last_user_msg)

    def _find_last_user_message(self, chat_id: str) -> str:
        """Return the most recent user message text for a chat.

        Args:
            chat_id: The chat id.

        Returns:
            The last user message content, or an empty string.
        """
        chat = chat_manager.get_chat(chat_id)
        messages = list(chat.messages) if chat else []
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return normalize_content(msg.get("content", ""))
        stored = self.app.chat_store.load_chat(chat_id)
        for msg in reversed((stored or {}).get("messages", [])):
            if msg.get("role") == "user":
                return normalize_content(msg.get("content", ""))
        return ""

    def _trim_stored_chat(self, chat_id: str) -> None:
        """Remove the trailing user turn from the stored chat.

        Args:
            chat_id: The chat id to trim.
        """
        stored = self.app.chat_store.load_chat(chat_id)
        if not stored:
            return
        messages = list(stored.get("messages", []))
        while messages and messages[-1].get("role") != "user":
            messages.pop()
        if messages and messages[-1].get("role") == "user":
            messages.pop()
        stored["messages"] = messages
        stored["message_count"] = len(messages)
        self.app.chat_store.save_chat(chat_id, stored)

    # ------------------------------------------------------------------
    #  Approval
    # ------------------------------------------------------------------

    async def _handle_approval(self, chat_id: str, event: dict, state: ChatState) -> None:
        """Show the approval bar and block until the user resolves it.

        Args:
            chat_id: The chat awaiting approval.
            event: The ``tool_call`` event dict.
            state: The chat's UI state.
        """
        state.approval_event = asyncio.Event()
        state.pending_tool_info = event
        state.approval_text = f"Approve {event.get('name', '')}?"
        self._refresh_sidebar()
        if self._is_visible(chat_id):
            self._rebuild_chat_display(chat_id)
            self._approval_text = state.approval_text
            self._set_approval_visible(True)
        self.chat_state_changed.emit(chat_id)
        await state.approval_event.wait()
        state.pending_tool_info = None
        state.approval_text = ""
        self._refresh_sidebar()
        if self._is_visible(chat_id):
            self._set_approval_visible(False)
        self.chat_state_changed.emit(chat_id)

    def _set_approval_visible(self, visible: bool) -> None:
        """Show or hide the approval bar.

        Args:
            visible: ``True`` to show, ``False`` to hide.
        """
        if self._approval_visible == visible:
            return
        self._approval_visible = visible
        self.approval_visibility_changed.emit(visible)

    # ------------------------------------------------------------------
    #  Compaction
    # ------------------------------------------------------------------

    async def _compact_chat(self, chat_id: str, chat: Agent) -> None:
        """Summarise an over-limit chat and start a fresh one.

        Args:
            chat_id: The chat that exceeded its limit.
            chat: The live agent chat to summarise.
        """
        limit = chat.check_limit_exceeded()
        if limit is None:
            return
        logger.info(
            "Agent[%s] exceeded limit (%s) — compacting",
            chat_id,
            limit.get("reason", ""),
        )
        if self._is_visible(chat_id):
            self.toast_requested.emit(
                "Chat limit reached — summarizing and starting a new chat…", TOAST_ERROR
            )
        summary = await chat.summarize()
        if not summary:
            if self._is_visible(chat_id):
                self.toast_requested.emit("Chat summarization failed.", TOAST_ERROR)
            return
        await self._create_compacted_chat(chat_id, summary)

    async def _create_compacted_chat(self, chat_id: str, summary: str) -> None:
        """Create a new chat seeded with a summary of the old one.

        Args:
            chat_id: The summarised chat id.
            summary: The summary text to seed the new chat with.
        """
        old = self.app.chat_store.load_chat(chat_id)
        skills_config = (old or {}).get("skills_config", {})
        new_id = self.session._generate_unique_chat_id()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.app.chat_store.save_chat(
            new_id,
            {
                "id": new_id,
                "skills_config": skills_config,
                "messages": [{"role": "user", "content": summary}],
                "session": (old or {}).get("session"),
                "created_at": now,
                "updated_at": now,
                "message_count": 1,
                "context_snapshot": (old or {}).get("context_snapshot", {}),
                "model_name": (old or {}).get("model_name") or self.app.config.llm_model_name,
                "summary_of": chat_id,
            },
        )
        self.session.open_chat_after(chat_id, new_id)
        logger.info("Started compacted chat '%s' (summary of '%s')", new_id, chat_id)

    # ------------------------------------------------------------------
    #  Rendering: rebuild display
    # ------------------------------------------------------------------

    @Slot(str)
    def rebuild_chat_display(self, chat_id: str) -> None:
        """Rebuild a chat's chat display on behalf of another controller.

        Public entry point used by the skill controller after a config sync so a
        newly appended delta context banner becomes visible.

        Args:
            chat_id: The chat whose display should be rebuilt.
        """
        if not chat_id:
            return
        self._rebuild_chat_display(chat_id)

    def _compute_render_plan(
        self, chat_id: str
    ) -> tuple[list[str], list[dict], dict | None, _RenderIndices]:
        """Compute the render plan for a chat without touching models.

        Pure computation (hashing, markdown rendering, token counting) over the
        chat's messages; it does not mutate the chat state, so it is safe
        to run on a worker thread via ``asyncio.to_thread``.

        Args:
            chat_id: The chat to render.

        Returns:
            ``(keys, items, snapshot, indices)``; ``snapshot`` is the stored
            context snapshot, if any. ``indices`` carries the row locations of the
            streaming cards for the caller to apply on the GUI thread.
        """
        state = self.session.state(chat_id)
        stored = self.app.chat_store.load_chat(chat_id)
        snapshot = (stored or {}).get("context_snapshot")
        chat = chat_manager.get_chat(chat_id)
        if chat is not None:
            messages = list(chat.messages)
        else:
            messages = list((stored or {}).get("messages", []))
        keys = self._compute_render_keys(state, messages, snapshot)
        items, indices = self._build_items(state, messages, snapshot)
        return keys, items, snapshot, indices

    def _apply_render_indices(self, state: ChatState, indices: _RenderIndices) -> None:
        """Apply a render plan's streaming-card row indices to the chat state.

        Args:
            state: The chat's UI state.
            indices: The indices produced by :meth:`_build_items`.
        """
        state.thinking.item_index = indices.thinking_index
        state.response.item_index = indices.response_index
        state.tool_call_indices = list(indices.tool_call_indices)

    def _rebuild_chat_display(self, chat_id: str) -> None:
        """Rebuild the chat model from the chat's message list.

        The render plan is hashed into keys; the model is diffed so only rows
        after the first divergence are replaced. Context banners (initial snapshot
        and delta updates) are emitted as the leading render-plan rows.

        Args:
            chat_id: The chat to render.
        """
        self._skip_staged_build()
        state = self.session.state(chat_id)
        model = self.model_for(chat_id)
        keys, items, snapshot, indices = self._compute_render_plan(chat_id)
        self._apply_render_indices(state, indices)
        model.diff_update(items, keys)
        state.rendered_item_keys = keys
        if snapshot:
            state.init_banner_displayed = True
        if self._is_visible(chat_id):
            self._update_token_bar(chat_id, state)

    async def _rebuild_chat_display_staged(self, chat_id: str) -> None:
        """Build a chat's chat model in batches while its overlay is shown.

        The chat list is non-virtualized, so inserting every card at once blocks
        the GUI thread for the whole build. Rows are inserted
        :data:`_RENDER_INSERT_BATCH` at a time with a short tick between batches so
        the GUI thread (and the loading scanner) keeps running; the caller keeps
        the list hidden until this returns. The plan itself (hashing, markdown
        rendering, token counting) is computed on a worker thread first, so the
        scanner keeps animating while it is prepared. A user action
        (:meth:`_skip_staged_build`) or a new switch (:meth:`_cancel_staged_build`)
        ends the build early.

        Args:
            chat_id: The chat to render.
        """
        state = self.session.state(chat_id)
        plan = await asyncio.to_thread(self._compute_render_plan, chat_id)
        if not self._is_visible(chat_id):
            return
        keys, items, snapshot, indices = plan
        self._apply_render_indices(state, indices)
        model = self.model_for(chat_id)
        build = _StagedBuildState(chat_id, model, state, items, keys)
        self._staged_build = build
        model.set_items([], [])
        total = len(items)
        batch_count = max(1, (total + _RENDER_INSERT_BATCH - 1) // _RENDER_INSERT_BATCH)
        tick = min(_RENDER_TICK_MAX, max(_RENDER_TICK_MIN, _RENDER_TICK_TARGET / batch_count))
        while not build.done and build.next_index < total:
            if self._staged_build is not build or not self._is_visible(chat_id):
                return
            end = min(build.next_index + _RENDER_INSERT_BATCH, total)
            model.append_items(items[build.next_index : end], keys[build.next_index : end])
            build.next_index = end
            if build.next_index < total:
                await asyncio.sleep(tick)
        if not build.done:
            state.rendered_item_keys = keys
            if snapshot:
                state.init_banner_displayed = True
        if self._staged_build is build:
            self._staged_build = None
            if not build.done and self._is_visible(chat_id):
                self._update_token_bar(chat_id, state)

    def _skip_staged_build(self) -> None:
        """Flush any in-progress staged build immediately.

        Called before a user action (send/regenerate/stop) or a synchronous
        rebuild so the remaining cards never interleave with the new rows.
        """
        build = self._staged_build
        if build is None or build.done:
            return
        start = build.next_index
        build.model.append_items(build.items[start:], build.keys[start:])
        build.next_index = len(build.items)
        build.done = True

    def _cancel_staged_build(self) -> None:
        """Drop an in-progress staged build without flushing (a rebuild replaces it)."""
        self._staged_build = None

    def _compute_render_keys(
        self, state: ChatState, messages: list[dict], snapshot: dict | None
    ) -> list[str]:
        """Compute content-hash keys for incremental render planning.

        Args:
            state: The chat's UI state.
            messages: The chat message list.
            snapshot: The stored context snapshot, if any. A truthy snapshot emits
                the initial "Original System Context" banner key.

        Returns:
            List of render-plan keys, one per emitted item.
        """
        keys: list[str] = []
        if snapshot:
            keys.append("b:i")
        for banner in state.context_banners_data:
            keys.append("b:d:" + _content_hash(json.dumps(banner, sort_keys=True)))
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            is_last_busy = state.is_busy and i == len(messages) - 1 and role == "assistant"
            if role == "user":
                keys.append("u:" + _content_hash(msg.get("content", "")))
            elif role == "assistant":
                keys.extend(_compute_assistant_keys(msg, messages, i, is_last_busy))
            elif role == "tool":
                name = msg.get("name", "")
                keys.append("tr:" + name + ":" + _content_hash(msg.get("content", "")))
        if _is_waiting_for_assistant(state, messages):
            keys.append("w:pending")
        return keys

    def _build_items(
        self, state: ChatState, messages: list[dict], snapshot: dict | None
    ) -> tuple[list[dict], _RenderIndices]:
        """Build the full list of chat items for the message list.

        Args:
            state: The chat's UI state.
            messages: The chat message list.
            snapshot: The stored context snapshot, if any.

        Returns:
            ``(items, indices)`` — role-keyed chat items aligned with
            :meth:`_compute_render_keys`, plus the streaming-card row indices for
            the caller to apply on the GUI thread.
        """
        indices = _RenderIndices()
        items: list[dict] = []
        if snapshot:
            items.append(
                build_context_banner_item(
                    "Original System Context",
                    build_context_sections_from_snapshot(snapshot),
                    is_delta=False,
                )
            )
        for banner in state.context_banners_data:
            items.append(
                build_context_banner_item(
                    banner.get("title", "Context Update"),
                    banner.get("sections", []),
                    is_delta=banner.get("is_delta", True),
                )
            )
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            is_last_busy = state.is_busy and i == len(messages) - 1 and role == "assistant"
            if role == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = _extract_text_from_multimodal(content)
                items.append(build_user_item(content))
            elif role == "assistant":
                self._build_assistant_items(state, msg, messages, i, is_last_busy, items, indices)
            elif role == "tool":
                content = msg.get("content", "")
                items.append(
                    build_tool_result_item(
                        msg.get("name", ""), content, token_count=count_tokens(content)
                    )
                )
        if _is_waiting_for_assistant(state, messages):
            items.append(build_waiting_item())
        return items, indices

    def _build_assistant_items(
        self,
        state: ChatState,
        msg: dict,
        messages: list[dict],
        idx: int,
        is_last_busy: bool,
        items: list[dict],
        indices: _RenderIndices,
    ) -> None:
        """Append the items for one assistant message.

        Args:
            state: The chat's UI state.
            msg: The assistant message dict.
            messages: Full message list.
            idx: Current message index.
            is_last_busy: Whether this is the last message and the chat is busy.
            items: Item accumulator.
            indices: Streaming-card index accumulator.
        """
        d = _assistant_decision(msg)
        if is_last_busy:
            self._build_streaming_assistant_items(state, d, messages, idx, items, indices)
            return
        if d["thinking_text"]:
            items.append(
                build_thinking_item(
                    d["thinking_text"], token_count=count_tokens(d["thinking_text"])
                )
            )
        if d["content_text"]:
            items.append(
                build_response_item(d["content_text"], token_count=count_tokens(d["content_text"]))
            )
        for tc in d["effective_tool_calls"]:
            entry = {
                "name": tc.get("function", {}).get("name", ""),
                "arguments": _parse_tool_arguments(tc),
                "mode": tc.get("_mode", "ask"),
            }
            args_str = tc.get("function", {}).get("arguments", "{}")
            items.append(build_tool_call_item(entry, token_count=count_tokens(args_str)))

    def _build_streaming_assistant_items(
        self,
        state: ChatState,
        d: dict[str, Any],
        messages: list[dict],
        idx: int,
        items: list[dict],
        indices: _RenderIndices,
    ) -> None:
        """Append streaming items (with pending cards) for the busy assistant.

        Args:
            state: The chat's UI state.
            d: The assistant decision dict from :func:`_assistant_decision`.
            messages: Full message list.
            idx: Current message index.
            items: Item accumulator.
            indices: Streaming-card index accumulator.
        """
        if d["thinking_text"]:
            if d["thinking_done"]:
                items.append(
                    build_thinking_item(
                        d["thinking_text"], token_count=count_tokens(d["thinking_text"])
                    )
                )
            else:
                indices.thinking_index = len(items)
                items.append(
                    build_thinking_pending_item(
                        d["thinking_text"], token_count=state.thinking.token_count
                    )
                )
        if d["content_text"]:
            if d["response_done"]:
                items.append(
                    build_response_item(
                        d["content_text"], token_count=count_tokens(d["content_text"])
                    )
                )
            else:
                indices.response_index = len(items)
                items.append(
                    build_response_pending_item(
                        d["content_text"], token_count=state.response.token_count
                    )
                )
        for tc in d["effective_tool_calls"]:
            tc_id = tc.get("id", "")
            name = tc.get("function", {}).get("name", "")
            mode = tc.get("_mode", "ask")
            args_str = tc.get("function", {}).get("arguments", "{}")
            indices.tool_call_indices.append(len(items))
            if tc_id in d["finalized_ids"]:
                entry = {"name": name, "arguments": _parse_tool_arguments(tc), "mode": mode}
                items.append(build_tool_call_item(entry, token_count=count_tokens(args_str)))
            else:
                items.append(build_tool_call_pending_item(name, mode, count_tokens(args_str)))
        if d["tool_calls"]:
            result_count = _count_trailing_tool_results(messages, idx)
            for k in range(result_count, len(d["tool_calls"])):
                tc = d["tool_calls"][k]
                items.append(
                    build_tool_result_pending_item(
                        tc.get("function", {}).get("name", ""), tc.get("id", "")
                    )
                )

    # ------------------------------------------------------------------
    #  Rendering: append / swap / live update
    # ------------------------------------------------------------------

    def _append_user_message(self, chat_id: str, text: str) -> None:
        """Optimistically append a user message item to a chat's model.

        Args:
            chat_id: The chat to append to.
            text: User message text.
        """
        if not chat_id:
            return
        model = self.model_for(chat_id)
        model.append_item(build_user_item(text), "u:" + _content_hash(text))

    def _append_waiting_placeholder(self, chat_id: str) -> None:
        """Optimistically append the pre-response scanner to a chat's model.

        Appended in the same frame as the user card so the scanner is visible
        immediately, before the blocking chat hydration and the network
        request. The render plan emits the matching ``w:pending`` key while
        waiting, so a later rebuild leaves the row untouched; the first streamed
        card replaces it.

        Args:
            chat_id: The chat to append to.
        """
        if not chat_id:
            return
        model = self.model_for(chat_id)
        model.append_item(build_waiting_item(), "w:pending")

    def _swap_pending_result_card(
        self, chat_id: str, tool_call_id: str, tool_name: str, content: str
    ) -> None:
        """Replace a pending tool-result card with the real result in place.

        Args:
            chat_id: The chat whose card to replace.
            tool_call_id: The tool-call id to match.
            tool_name: Tool name for the real result card.
            content: Result content text.
        """
        if not chat_id:
            return
        model = self._models.get(chat_id)
        if model is None:
            return
        row = model.find_pending_result(tool_call_id)
        if row < 0:
            self._rebuild_chat_display(chat_id)
            return
        item = build_tool_result_item(tool_name, content, token_count=count_tokens(content))
        model.replace_item(row, item, "tr:" + tool_name + ":" + _content_hash(content))

    def _update_live_assistant(self, chat_id: str, state: ChatState) -> None:
        """Live render the streaming assistant message with a short throttle.

        Structural changes (tool calls/results appearing, streaming tool calls
        first appearing) rebuild immediately. A pending thinking/response card is
        rebuilt into existence the first time its text arrives. Content-only
        updates are throttled to :data:`_STREAM_UPDATE_INTERVAL` and applied in
        place via ``update_item``.

        Args:
            chat_id: The chat being rendered.
            state: The chat's UI state.
        """
        model = self._models.get(chat_id)
        if not chat_id or model is None or model.count() == 0:
            return
        chat = chat_manager.get_chat(chat_id)
        if not chat:
            return
        messages = chat.messages
        if not messages or messages[-1].get("role") != "assistant":
            return
        last_msg = messages[-1]
        decision = _assistant_decision(last_msg)
        thinking_text = decision["thinking_text"]
        content_text = decision["content_text"]
        thinking_changed = thinking_text != state.last_rendered_thinking_text
        content_changed = content_text != state.last_rendered_message_text
        tool_calls_changed = len(last_msg.get("tool_calls", [])) != state.last_rendered_tool_calls
        tool_results_changed = len(state.tool_results) != state.last_rendered_tool_results
        streaming_tcs = last_msg.get("_streaming_tool_calls")
        streaming_tc_json = json.dumps(streaming_tcs) if streaming_tcs else ""
        streaming_tc_changed = (
            bool(streaming_tcs) and streaming_tc_json != state.last_rendered_streaming_tc_json
        )
        streaming_tc_needs_rebuild = streaming_tc_changed and not state.tool_call_indices
        now = time.monotonic()

        if tool_calls_changed or tool_results_changed or streaming_tc_needs_rebuild:
            state.last_rebuild_time = now
            self._rebuild_chat_display(chat_id)
            self._track_rendered_state(chat_id, state)
            return
        missing_pending_card = (
            thinking_text and not decision["thinking_done"] and state.thinking.item_index is None
        ) or (content_text and not decision["response_done"] and state.response.item_index is None)
        if missing_pending_card:
            state.last_rebuild_time = now
            self._rebuild_chat_display(chat_id)
            self._track_rendered_state(chat_id, state)
            return
        content_only = thinking_changed or content_changed
        streaming_active = streaming_tc_changed and bool(state.tool_call_indices)
        if not (content_only or streaming_active):
            return
        if now - state.last_content_update_time < _STREAM_UPDATE_INTERVAL:
            self._track_rendered_state(chat_id, state)
            return
        state.last_content_update_time = now
        self._apply_streaming_item_updates(
            chat_id,
            state,
            thinking_text,
            content_text,
            streaming_tcs,
            thinking_changed,
            content_changed,
        )
        self._track_rendered_state(chat_id, state)

    def _apply_streaming_item_updates(
        self,
        chat_id: str,
        state: ChatState,
        thinking_text: str,
        content_text: str,
        streaming_tcs: list | None,
        thinking_changed: bool,
        content_changed: bool,
    ) -> None:
        """Apply throttled content-only updates to the streaming card rows.

        Re-renders the accumulated thinking/response markdown into ``BODY_HTML``
        and refreshes the header token text and live tool-call token counts.

        Args:
            chat_id: The chat being rendered.
            state: The chat's UI state.
            thinking_text: Current thinking text.
            content_text: Current response text.
            streaming_tcs: Live streaming tool calls, if any.
            thinking_changed: Whether the thinking text changed.
            content_changed: Whether the response text changed.
        """
        model = self._models.get(chat_id)
        if model is None:
            return
        if thinking_changed:
            state.thinking.token_count = _accumulate_tokens(
                thinking_text, state.last_tok_counted_thinking, state.thinking.token_count
            )
            state.last_tok_counted_thinking = thinking_text
            if state.thinking.item_index is not None:
                model.update_item(
                    state.thinking.item_index,
                    {
                        int(ChatRole.BODY_HTML): render_markdown(thinking_text),
                        int(ChatRole.TOKEN_TEXT): f"{state.thinking.token_count} tk",
                    },
                )
        if content_changed:
            state.response.token_count = _accumulate_tokens(
                content_text, state.last_tok_counted_response, state.response.token_count
            )
            state.last_tok_counted_response = content_text
            if state.response.item_index is not None:
                model.update_item(
                    state.response.item_index,
                    {
                        int(ChatRole.BODY_HTML): render_markdown(content_text),
                        int(ChatRole.TOKEN_TEXT): f"{state.response.token_count} tk",
                    },
                )
        if streaming_tcs:
            for idx, tc in enumerate(streaming_tcs):
                if idx >= len(state.tool_call_indices):
                    break
                args_str = tc.get("function", {}).get("arguments", "{}")
                model.update_item(
                    state.tool_call_indices[idx],
                    {int(ChatRole.TOKEN_TEXT): f"{count_tokens(args_str)} tk"},
                )

    def _track_rendered_state(self, chat_id: str, state: ChatState) -> None:
        """Store the currently rendered streaming state for diff detection.

        Args:
            state: The chat's UI state to update.
        """
        if not chat_id:
            return
        chat = chat_manager.get_chat(chat_id)
        if chat and chat.messages:
            last = chat.messages[-1]
            if last.get("role") == "assistant":
                state.last_rendered_thinking_text = last.get("reasoning_content", "")
                state.last_rendered_message_text = last.get("content", "") or ""
                state.last_rendered_tool_calls = len(last.get("tool_calls", []))
                state.last_rendered_tool_results = len(state.tool_results)
                streaming_tcs = last.get("_streaming_tool_calls")
                state.last_rendered_streaming_tc_json = (
                    json.dumps(streaming_tcs) if streaming_tcs else ""
                )

    # ------------------------------------------------------------------
    #  State: token bar / buttons / loading
    # ------------------------------------------------------------------

    def _update_token_bar(self, chat_id: str, state: ChatState | None = None) -> None:
        """Update the token counts shown for a chat.

        Args:
            chat_id: The chat whose tokens to show.
            state: Optional chat state carrying true API token counts.
        """
        if not chat_id:
            return
        if state and state.true_input_tokens > 0:
            ctx = state.true_input_tokens
            out = state.true_output_cum
        else:
            chat = chat_manager.get_chat(chat_id)
            ctx = chat._estimated_total if chat else 0
            out = 0
        self._set_token_counts(ctx, out)

    def _set_token_counts(self, input_tokens: int, output_tokens: int) -> None:
        """Store and emit new token counts.

        Args:
            input_tokens: Context (input) token count.
            output_tokens: Cumulative output token count.
        """
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.token_counts_changed.emit(input_tokens, output_tokens)

    def _update_button_state(self, chat_id: str = "") -> None:
        """Reflect a chat's busy state on the legacy focused busy property.

        Args:
            chat_id: The chat to reflect.
        """
        target = chat_id or self.active_chat_id
        state = self.session.state(target) if target else None
        is_busy = bool(state and state.is_busy)
        if self._busy == is_busy:
            return
        self._busy = is_busy
        self.busy_changed.emit(is_busy)

    def _set_loading(self, chat_id: str, loading: bool) -> None:
        """Set a chat's switch rebuild loading flag.

        Args:
            chat_id: The chat whose loading flag to set.
            loading: Whether a switch rebuild is in progress.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        if state.is_loading == loading:
            return
        state.is_loading = loading
        self.chat_state_changed.emit(chat_id)
