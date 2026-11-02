"""``ChatController`` — per-chat models, streaming apply, and lifecycle.

Each chat's ``Agent`` and render pipeline run on a dedicated
:class:`~src.qt.chat_worker.ChatWorker` thread.  This controller stays on the
GUI thread: it owns one :class:`ChatListModel` per chat, forwards user actions
as worker commands, and applies the ready row updates the workers emit.  Agents
and message ownership live on the workers, never here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import hashlib
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Property, QObject, Signal, Slot

from .chat_items import build_user_item, build_waiting_item
from .chat_render import delete_bounds
from .chat_worker import (
    ChatWorker,
    ensure_worker,
    get_worker,
    stop_all_workers,
)
from .error_handler import TOAST_ERROR
from .models.chat_list_model import ChatListModel
from .render_pool import shutdown_render_pool

if TYPE_CHECKING:
    from ..app import ProcooApp
    from ..chat.agent import Agent
    from .chat_state import ChatState
    from .session_controller import SessionController

logger = logging.getLogger("procoo_qt")

#: Delay (seconds) after a chat switch before the transcript rebuild starts.
_REBUILD_PAINT_DELAY = 0.02

#: Quiet period (seconds) before the sidebar refresh rebuilds chat summaries.
_SIDEBAR_REFRESH_DEBOUNCE = 0.3

#: Staged insert batch size while a switch loading overlay is showing.
_RENDER_INSERT_BATCH = 16
_RENDER_TICK_MIN = 0.004
_RENDER_TICK_MAX = 0.016
_RENDER_TICK_TARGET = 0.25

#: Gentler insert schedule for background pre-warm (no overlay, GUI must stay
#: responsive while QML lays out the pre-built cards).
_PREWARM_INSERT_BATCH = 4
_PREWARM_TICK = 0.05


def _content_hash(data: str | list) -> str:
    """Return a short stable content hash for optimistic row keys.

    Args:
        data: A string or a JSON-serializable list.

    Returns:
        A 16-character blake2b hex digest.
    """
    if isinstance(data, list):
        import json

        data = json.dumps(data, sort_keys=True)
    return hashlib.blake2b(data.encode()).hexdigest()[:16]


class ChatController(QObject):
    """Per-chat model cache, worker lifecycle, and streaming apply."""

    active_model_changed = Signal()
    approval_visibility_changed = Signal(bool)
    token_counts_changed = Signal(int, int)
    toast_requested = Signal(str, str)
    busy_changed = Signal(bool)
    loading_changed = Signal(bool)
    chat_state_changed = Signal(str)
    chat_tokens_changed = Signal(str)
    config_updated = Signal(str, object)

    if TYPE_CHECKING:
        app: ProcooApp
        session: SessionController

        _models: dict[str, ChatListModel]
        _tasks: set[asyncio.Task[Any]]
        _visible_chat_ids: set[str]
        _prewarm_chats: set[str]
        _prewarm_tokens: dict[str, int]
        _prewarm_futures: dict[str, asyncio.Future[None]]
        _rendered_chats: set[str]
        active_chat_id: str | None
        _approval_visible: bool
        _approval_text: str
        _busy: bool
        _loading: bool
        _input_tokens: int
        _output_tokens: int

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
        self._connected_workers: dict[str, ChatWorker] = {}
        self._switch_generations: dict[str, int] = {}
        self._staged_tokens: dict[str, int] = {}
        self._prewarm_chats: set[str] = set()
        self._prewarm_tokens: dict[str, int] = {}
        self._prewarm_futures: dict[str, asyncio.Future[None]] = {}
        self._rendered_chats: set[str] = set()
        self.active_chat_id = None
        self._approval_visible = False
        self._approval_text = ""
        self._busy = False
        self._loading = False
        self._input_tokens = 0
        self._output_tokens = 0
        self._sidebar_dirty = False
        self._sidebar_task: asyncio.Task[Any] | None = None

    def build(self) -> None:
        """Reset the per-chat model cache."""
        self._models = {}
        self._visible_chat_ids = set()
        self._connected_workers = {}
        self._switch_generations = {}
        self._prewarm_chats = set()
        self._prewarm_tokens = {}
        self._prewarm_futures = {}
        self._rendered_chats = set()
        self.active_chat_id = None

    def shutdown(self) -> None:
        """Stop every chat worker and the render pool (application shutdown)."""
        stop_all_workers()
        shutdown_render_pool()
        self._connected_workers = {}

    # ------------------------------------------------------------------
    #  Public: visible panels
    # ------------------------------------------------------------------

    def set_visible_chats(self, chat_ids: set[str]) -> None:
        """Record which chats are currently shown in a panel.

        Args:
            chat_ids: The active chat id of every visible panel.
        """
        self._visible_chat_ids = set(chat_ids)
        for chat_id, worker in self._connected_workers.items():
            worker.set_visible(self._is_visible(chat_id))

    def _is_visible(self, chat_id: str) -> bool:
        """Return whether a chat is currently shown.

        Args:
            chat_id: The chat id to test.

        Returns:
            ``True`` if the chat is in a visible panel.
        """
        return chat_id in self._visible_chat_ids

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=active_model_changed)
    def activeModel(self) -> ChatListModel | None:  # noqa: N802
        """Return the chat model for the active chat."""
        if self.active_chat_id is None:
            return None
        return self._models.get(self.active_chat_id)

    @Property(bool, notify=approval_visibility_changed)
    def approvalVisible(self) -> bool:  # noqa: N802
        """Return whether the approval bar is shown."""
        return self._approval_visible

    @Property(str, notify=approval_visibility_changed)
    def approvalText(self) -> str:  # noqa: N802
        """Return the approval prompt text."""
        return self._approval_text

    @Property(bool, notify=busy_changed)
    def busy(self) -> bool:
        """Return whether the active chat is generating."""
        return self._busy

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        """Return whether a chat switch rebuild is in progress."""
        return self._loading

    @Property(int, notify=token_counts_changed)
    def inputTokens(self) -> int:  # noqa: N802
        """Return the active chat's input token count."""
        return self._input_tokens

    @Property(int, notify=token_counts_changed)
    def outputTokens(self) -> int:  # noqa: N802
        """Return the active chat's cumulative output token count."""
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

    def attach_worker(self, chat_id: str, agent: Agent) -> ChatWorker:
        """Ensure a worker exists for a chat and wire its signals.

        Args:
            chat_id: The chat id.
            agent: The live agent.

        Returns:
            The running worker.
        """
        worker = ensure_worker(chat_id, agent, self.app)
        if self._connected_workers.get(chat_id) is not worker:
            worker.plan_ready.connect(self._on_plan_ready)
            worker.stream_updated.connect(self._on_stream_updated)
            worker.result_swap.connect(self._on_result_swap)
            worker.turn_started.connect(self._on_turn_started)
            worker.turn_finished.connect(self._on_turn_finished)
            worker.approval_needed.connect(self._on_approval_needed)
            worker.approval_cleared.connect(self._on_approval_cleared)
            worker.token_usage.connect(self._on_token_usage)
            worker.error.connect(self._on_error)
            worker.message_count.connect(self._on_message_count)
            worker.compaction_ready.connect(self._on_compaction_ready)
            worker.config_updated.connect(self._on_config_updated)
            self._connected_workers[chat_id] = worker
        worker.set_visible(self._is_visible(chat_id))
        return worker

    def _refresh_sidebar(self) -> None:
        """Schedule a debounced, off-thread refresh of the chat sidebar."""
        self._sidebar_dirty = True
        if self._sidebar_task is None or self._sidebar_task.done():
            self._sidebar_task = asyncio.ensure_future(self._refresh_sidebar_loop())

    async def _refresh_sidebar_loop(self) -> None:
        """Wait for a quiet period, then reload summaries on a worker thread."""
        while True:
            self._sidebar_dirty = False
            await asyncio.sleep(_SIDEBAR_REFRESH_DEBOUNCE)
            if self._sidebar_dirty:
                continue
            await self.session.refresh_model_async()
            if not self._sidebar_dirty:
                break

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
        self._append_user_message(chat_id, message)
        self._launch_generation(chat_id, message)

    # ------------------------------------------------------------------
    #  Slot: Stop / Regenerate / Approve / Deny / Delete
    # ------------------------------------------------------------------

    @Slot()
    def _handle_stop(self) -> None:
        """Stop the focused chat's generation."""
        self._handle_stop_for(self.active_chat_id or "")

    @Slot(str)
    def _handle_stop_for(self, chat_id: str) -> None:
        """Stop a specific chat's generation.

        Args:
            chat_id: The chat to stop.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        if state.is_busy:
            state.has_error = True
        worker = get_worker(chat_id)
        if worker is not None:
            worker.cancel_turn()
        self._on_approval_cleared(chat_id)
        logger.info("Generation stopped by user in chat '%s'", chat_id)

    @Slot()
    def _handle_regenerate(self) -> None:
        """Regenerate the last user message in the focused chat."""
        self._handle_regenerate_for(self.active_chat_id or "")

    @Slot(str)
    def _handle_regenerate_for(self, chat_id: str) -> None:
        """Regenerate the last user message in a specific chat.

        Args:
            chat_id: The chat to regenerate.
        """
        if not chat_id:
            self.toast_requested.emit("Please create or select a chat first.", TOAST_ERROR)
            return
        self._spawn(self._regenerate(chat_id))

    @Slot(str, int)
    def _handle_delete_turn_for(self, chat_id: str, msg_index: int) -> None:
        """Delete the message object behind a chat card from history.

        Args:
            chat_id: The chat whose card was clicked.
            msg_index: Index of the source message.
        """
        if not chat_id or msg_index < 0:
            return
        state = self.session.state(chat_id)
        if state.is_busy:
            self.toast_requested.emit("Please wait for the current response.", TOAST_ERROR)
            return
        worker = get_worker(chat_id)
        if worker is not None:
            worker.delete_turn(msg_index)
        else:
            self._delete_stored_turn(chat_id, msg_index)

    @Slot(str, int)
    def _handle_regenerate_from_for(self, chat_id: str, msg_index: int) -> None:
        """Regenerate starting from a specific user card.

        Args:
            chat_id: The chat whose card was clicked.
            msg_index: Index of the source user message.
        """
        if not chat_id:
            self.toast_requested.emit("Please create or select a chat first.", TOAST_ERROR)
            return
        self._spawn(self._regenerate_from(chat_id, msg_index))

    @Slot()
    def _handle_approve(self) -> None:
        """Approve the focused chat's pending tool call."""
        self._handle_approve_for(self.active_chat_id or "")

    @Slot(str)
    def _handle_approve_for(self, chat_id: str) -> None:
        """Approve a specific chat's pending tool call.

        Args:
            chat_id: The chat whose tool call to approve.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        info = state.pending_tool_info
        if not info:
            return
        worker = get_worker(chat_id)
        if worker is not None:
            worker.confirm_approval(info.get("id", ""))
        self._on_approval_cleared(chat_id)

    @Slot(str)
    def _handle_deny(self, reason: str) -> None:
        """Deny the focused chat's pending tool call."""
        self._handle_deny_for(self.active_chat_id or "", reason)

    @Slot(str, str)
    def _handle_deny_for(self, chat_id: str, reason: str) -> None:
        """Deny a specific chat's pending tool call.

        Args:
            chat_id: The chat whose tool call to deny.
            reason: Optional denial reason typed by the user.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        info = state.pending_tool_info
        if not info:
            return
        worker = get_worker(chat_id)
        if worker is not None:
            worker.deny_approval(info.get("id", ""), (reason or "").strip())
        self._on_approval_cleared(chat_id)

    # ------------------------------------------------------------------
    #  Public: Panel rebuild
    # ------------------------------------------------------------------

    def prepare_rebuild(self, chat_id: str) -> None:
        """Show a chat's loading overlay and blank its model before rebinding.

        Only a cold model (no rows yet) is blanked and given the overlay. A
        populated model is left intact so switching back to a chat that was
        already rendered does not destroy its delegates or flash a spinner.

        Args:
            chat_id: The chat whose panel is being recreated.
        """
        if not chat_id:
            return
        if not self._model_needs_build(chat_id):
            return
        self._set_loading(chat_id, True)
        self.model_for(chat_id).set_items([], [])

    def _model_needs_build(self, chat_id: str) -> bool:
        """Return whether a chat has no rendered rows yet.

        Args:
            chat_id: The chat to test.

        Returns:
            ``True`` when the chat's model is missing or empty.
        """
        model = self._models.get(chat_id)
        return model is None or model.count() == 0

    def rebuild_chat_display(self, chat_id: str) -> None:
        """Queue a background rebuild for a chat whose panel was rebound.

        A cold model is blanked and covered by the loading overlay; a populated
        model is left intact and the resulting plan is merged into it, so a
        split/move does not destroy an already-rendered transcript. Chats with
        no attached worker have nothing rendered yet, so they are skipped.

        Args:
            chat_id: The chat whose panel is being rebound.
        """
        if not chat_id:
            return
        worker = self._connected_workers.get(chat_id)
        if worker is None:
            return
        self.prepare_rebuild(chat_id)
        worker.request_rebuild()

    # ------------------------------------------------------------------
    #  Public: Transcript pre-warm
    # ------------------------------------------------------------------

    async def prewarm_chat(self, chat_id: str, timeout: float = 15.0) -> None:
        """Render a chat's transcript without showing it.

        Hydrates the chat, attaches its worker, and requests one plan. The plan
        is applied in background batches (no loading overlay) so the chat's QML
        transcript is fully built before the user switches to it.

        Args:
            chat_id: The chat to pre-render.
            timeout: Maximum seconds to wait for the plan to be applied.
        """
        if not chat_id or self._is_visible(chat_id):
            return
        if self.session.state(chat_id).is_busy:
            return
        model = self.model_for(chat_id)
        if model.count() > 0:
            self._rendered_chats.add(chat_id)
            return
        if chat_id in self._prewarm_chats:
            return
        agent = await self.session._hydrate_chat(chat_id, silent=True)
        if agent is None:
            return
        worker = self.attach_worker(chat_id, agent)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        self._prewarm_chats.add(chat_id)
        self._prewarm_tokens[chat_id] = self._prewarm_tokens.get(chat_id, 0) + 1
        self._prewarm_futures[chat_id] = future
        worker.request_prewarm_plan()
        try:
            await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            logger.warning("Transcript prewarm timed out for chat '%s'", chat_id)
        finally:
            self._prewarm_chats.discard(chat_id)
            self._prewarm_futures.pop(chat_id, None)
            self._prewarm_tokens[chat_id] = self._prewarm_tokens.get(chat_id, 0) + 1

    async def wait_until_ready(self, chat_id: str, timeout: float = 15.0) -> None:
        """Wait until a chat's first plan has been applied.

        Args:
            chat_id: The chat to wait for.
            timeout: Maximum seconds to wait.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while chat_id not in self._rendered_chats:
            if loop.time() >= deadline:
                return
            await asyncio.sleep(0.05)

    def forget_chat(self, chat_id: str) -> None:
        """Drop pre-warm/render bookkeeping for a deleted chat.

        Args:
            chat_id: The chat being deleted.
        """
        self._cancel_prewarm(chat_id)
        self._rendered_chats.discard(chat_id)
        self._prewarm_tokens.pop(chat_id, None)

    def cancel_prewarms(self) -> None:
        """Abort every in-flight transcript pre-warm."""
        for chat_id in list(self._prewarm_chats):
            self._cancel_prewarm(chat_id)

    def cancel_prewarm(self, chat_id: str) -> None:
        """Abort one chat's in-flight transcript pre-warm.

        Args:
            chat_id: The chat whose pre-warm should stop.
        """
        self._cancel_prewarm(chat_id)

    def _cancel_prewarm(self, chat_id: str) -> None:
        """Abort an in-flight pre-warm and clear its partial model.

        Args:
            chat_id: The chat whose pre-warm should stop.
        """
        if chat_id not in self._prewarm_chats:
            return
        self._prewarm_tokens[chat_id] = self._prewarm_tokens.get(chat_id, 0) + 1
        self._prewarm_chats.discard(chat_id)
        future = self._prewarm_futures.pop(chat_id, None)
        if future is not None and not future.done():
            future.set_result(None)
        model = self._models.get(chat_id)
        if model is not None:
            model.set_items([], [])

    async def _apply_plan_prewarm(
        self,
        chat_id: str,
        model: ChatListModel,
        items: list[dict],
        keys: list[str],
        token: int,
    ) -> None:
        """Apply a pre-warm plan in background batches without an overlay.

        Args:
            chat_id: The chat being pre-rendered.
            model: The model receiving rows.
            items: Role-keyed rows.
            keys: Per-row identity keys.
            token: The pre-warm token; a newer plan supersedes this one.
        """
        if self._prewarm_tokens.get(chat_id) != token:
            return
        model.set_items([], [])
        total = len(items)
        index = 0
        while index < total:
            if self._prewarm_tokens.get(chat_id) != token:
                return
            end = min(index + _PREWARM_INSERT_BATCH, total)
            model.append_items(items[index:end], keys[index:end])
            index = end
            if index < total:
                await asyncio.sleep(_PREWARM_TICK)
        if self._prewarm_tokens.get(chat_id) != token:
            return
        self._rendered_chats.add(chat_id)
        future = self._prewarm_futures.get(chat_id)
        if future is not None and not future.done():
            future.set_result(None)

    # ------------------------------------------------------------------
    #  Slot: Chat activated / switch started
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_chat_switch_started(self, chat_id: str) -> None:
        """Show the loading scanner as soon as a chat switch is requested.

        Args:
            chat_id: The chat being switched to.
        """
        if not chat_id:
            return
        self._cancel_prewarm(chat_id)
        if self._model_needs_build(chat_id):
            self._set_loading(chat_id, True)

    @Slot(str)
    def _handle_chat_activated(self, chat_id: str) -> None:
        """Focus a chat and rebuild its display.

        Args:
            chat_id: The newly activated chat id (empty when none).
        """
        self.active_chat_id = chat_id or None
        if not chat_id:
            self._set_approval_visible(False)
            self.active_model_changed.emit()
            return
        self._cancel_prewarm(chat_id)
        self.model_for(chat_id)
        self.active_model_changed.emit()
        if self._model_needs_build(chat_id):
            self._set_loading(chat_id, True)
        generation = self._switch_generations.get(chat_id, 0) + 1
        self._switch_generations[chat_id] = generation
        self._spawn(self._activate_async(chat_id, generation))

    async def _activate_async(self, chat_id: str, generation: int) -> None:
        """Hydrate the chat, attach its worker, and request a rebuild.

        Args:
            chat_id: The chat that was activated.
            generation: The switch generation this activation belongs to.
        """
        await asyncio.sleep(_REBUILD_PAINT_DELAY)
        agent = await self.session._hydrate_chat(chat_id)
        if agent is None:
            self._finish_switch_loading(chat_id, generation)
            return
        if self._switch_generations.get(chat_id, 0) != generation:
            return
        worker = self.attach_worker(chat_id, agent)
        worker.set_visible(True)
        if self._is_visible(chat_id):
            self.chat_state_changed.emit(chat_id)

    def _finish_switch_loading(self, chat_id: str, generation: int) -> None:
        """Clear a chat's switch loading flag unless a newer switch owns it.

        Args:
            chat_id: The chat whose overlay should be hidden.
            generation: The switch generation of the finishing activation.
        """
        if not chat_id:
            return
        if self._switch_generations.get(chat_id, 0) != generation:
            return
        self._set_loading(chat_id, False)

    # ------------------------------------------------------------------
    #  Generation lifecycle
    # ------------------------------------------------------------------

    def _launch_generation(self, chat_id: str, message: str) -> None:
        """Mark a chat busy, show the scanner, and start the worker turn.

        Args:
            chat_id: The chat to generate for.
            message: User message text to send.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        state.is_busy = True
        state.has_error = False
        state.generation_id += 1
        gen_id = state.generation_id
        self._append_waiting_placeholder(chat_id)
        self._refresh_sidebar()
        self.chat_state_changed.emit(chat_id)
        self._spawn(self._start_turn(chat_id, message, gen_id))

    async def _start_turn(self, chat_id: str, message: str, gen_id: int) -> None:
        """Hydrate the chat, attach the worker, and start one turn.

        Args:
            chat_id: The chat to run.
            message: The user message text.
            gen_id: Generation counter for stale-turn detection.
        """
        agent = await self.session._hydrate_chat(chat_id)
        if agent is None:
            state = self.session.state(chat_id)
            if state.generation_id == gen_id:
                state.is_busy = False
                state.has_error = True
                self.chat_state_changed.emit(chat_id)
                self._refresh_sidebar()
            return
        worker = self.attach_worker(chat_id, agent)
        worker.set_visible(self._is_visible(chat_id))
        worker.start_turn(message, gen_id)

    # ------------------------------------------------------------------
    #  Regenerate / delete
    # ------------------------------------------------------------------

    async def _regenerate(self, chat_id: str) -> None:
        """Trim the last user turn and re-send it through the worker.

        Args:
            chat_id: The chat to regenerate.
        """
        state = self.session.state(chat_id)
        if state.is_busy:
            self.toast_requested.emit("Please wait for the current response.", TOAST_ERROR)
            return
        agent = await self.session._hydrate_chat(chat_id)
        if agent is None:
            return
        state.is_busy = True
        state.has_error = False
        state.generation_id += 1
        gen_id = state.generation_id
        self.chat_state_changed.emit(chat_id)
        worker = self.attach_worker(chat_id, agent)
        worker.set_visible(self._is_visible(chat_id))
        worker.regenerate(gen_id)

    async def _regenerate_from(self, chat_id: str, msg_index: int) -> None:
        """Trim history to before a user message and regenerate from it.

        Args:
            chat_id: The chat to regenerate.
            msg_index: Index of the user message to re-send.
        """
        state = self.session.state(chat_id)
        if state.is_busy:
            self.toast_requested.emit("Please wait for the current response.", TOAST_ERROR)
            return
        agent = await self.session._hydrate_chat(chat_id)
        if agent is None:
            return
        messages = agent.messages
        if not 0 <= msg_index < len(messages) or messages[msg_index].get("role") != "user":
            self.toast_requested.emit("Can only regenerate from a user message.", TOAST_ERROR)
            return
        state.is_busy = True
        state.has_error = False
        state.generation_id += 1
        gen_id = state.generation_id
        self.chat_state_changed.emit(chat_id)
        worker = self.attach_worker(chat_id, agent)
        worker.set_visible(self._is_visible(chat_id))
        worker.regenerate_from(msg_index, gen_id)

    def _delete_stored_turn(self, chat_id: str, msg_index: int) -> None:
        """Delete a turn for a chat that has no live worker.

        Args:
            chat_id: The chat whose card was clicked.
            msg_index: Index of the source message.
        """
        stored = self.app.chat_store.load_chat(chat_id)
        messages = list((stored or {}).get("messages", []))
        if not 0 <= msg_index < len(messages):
            return
        start, end = delete_bounds(messages, msg_index)
        del messages[start:end]
        if stored:
            stored["messages"] = messages
            stored["message_count"] = len(messages)
            self.app.chat_store.save_chat(chat_id, stored)
        state = self.session.state(chat_id)
        state.message_count = len(messages)
        self._refresh_sidebar()

    # ------------------------------------------------------------------
    #  Worker signal handlers
    # ------------------------------------------------------------------

    @Slot(str, object)
    def _on_plan_ready(self, chat_id: str, plan: object) -> None:
        """Apply a full render plan emitted by a worker.

        Args:
            chat_id: The chat whose plan is ready.
            plan: The :class:`~src.qt.chat_render.RenderPlan`.
        """
        model = self.model_for(chat_id)
        state = self.session.state(chat_id)
        items = getattr(plan, "items", [])
        keys = getattr(plan, "keys", [])
        if chat_id in self._prewarm_chats:
            token = self._prewarm_tokens.get(chat_id, 0) + 1
            self._prewarm_tokens[chat_id] = token
            self._spawn(self._apply_plan_prewarm(chat_id, model, items, keys, token))
            if self._is_visible(chat_id):
                self._update_token_bar(chat_id, state)
            return
        divergence = model.find_divergence(keys)
        if divergence < 0:
            self._rendered_chats.add(chat_id)
            self._set_loading(chat_id, False)
        elif state.is_loading and (model.count() == 0 or chat_id in self._staged_tokens):
            token = self._staged_tokens.get(chat_id, 0) + 1
            self._staged_tokens[chat_id] = token
            self._spawn(self._apply_plan_staged(chat_id, model, items, keys, token))
        else:
            model.merge_items(items, keys)
            self._rendered_chats.add(chat_id)
            self._set_loading(chat_id, False)
        if self._is_visible(chat_id):
            self._update_token_bar(chat_id, state)

    async def _apply_plan_staged(
        self,
        chat_id: str,
        model: ChatListModel,
        items: list[dict],
        keys: list[str],
        token: int,
    ) -> None:
        """Insert a plan's rows in batches behind the loading overlay.

        Args:
            chat_id: The chat whose rows are being applied.
            model: The model receiving rows.
            items: Role-keyed rows.
            keys: Per-row identity keys.
            token: The staged-apply token; a newer apply supersedes this one.
        """
        model.set_items([], [])
        total = len(items)
        batch_count = max(1, (total + _RENDER_INSERT_BATCH - 1) // _RENDER_INSERT_BATCH)
        tick = min(_RENDER_TICK_MAX, max(_RENDER_TICK_MIN, _RENDER_TICK_TARGET / batch_count))
        index = 0
        while index < total:
            if self._staged_tokens.get(chat_id) != token:
                return
            end = min(index + _RENDER_INSERT_BATCH, total)
            model.append_items(items[index:end], keys[index:end])
            index = end
            if index < total:
                await asyncio.sleep(tick)
        if self._staged_tokens.get(chat_id) == token:
            self._staged_tokens.pop(chat_id, None)
            self._rendered_chats.add(chat_id)
            self._set_loading(chat_id, False)

    @Slot(str, object)
    def _on_stream_updated(self, chat_id: str, updates: object) -> None:
        """Apply in-place streaming row updates emitted by a worker.

        Args:
            chat_id: The chat being updated.
            updates: A list of ``(row, role_values)`` pairs.
        """
        state = self.session.state(chat_id)
        if state.is_loading:
            # A staged rebuild owns the model; index-based merges would corrupt
            # the partially built rows. The terminal plan reconciles instead.
            return
        model = self.model_for(chat_id)
        for row, values in cast(list, updates):
            model.update_item(row, values)

    @Slot(str, str, object, str)
    def _on_result_swap(self, chat_id: str, tool_id: str, item: object, key: str) -> None:
        """Replace a pending tool-result card in place.

        Args:
            chat_id: The chat to update.
            tool_id: The tool-call id to match.
            item: The real tool-result row.
            key: The row's new identity key.
        """
        model = self.model_for(chat_id)
        row = model.find_pending_result(tool_id)
        if row < 0:
            worker = get_worker(chat_id)
            if worker is not None:
                worker.request_rebuild()
            return
        model.replace_item(row, cast(dict, item), key)

    @Slot(str, int)
    def _on_turn_started(self, chat_id: str, gen_id: int) -> None:
        """Refresh GUI state when a worker turn begins.

        Args:
            chat_id: The chat that started.
            gen_id: The generation counter.
        """
        state = self.session.state(chat_id)
        state.is_busy = True
        self._refresh_sidebar()
        self.chat_state_changed.emit(chat_id)
        if self._is_visible(chat_id):
            self._update_button_state(chat_id)

    @Slot(str, int)
    def _on_turn_finished(self, chat_id: str, gen_id: int) -> None:
        """Clear busy state and refresh once a worker turn ends.

        Args:
            chat_id: The chat that finished.
            gen_id: The generation counter for stale-turn detection.
        """
        state = self.session.state(chat_id)
        if state.generation_id == gen_id:
            state.is_busy = False
            state.reset_turn()
        self.session.mark_chat_updated(chat_id)
        self._refresh_sidebar()
        self.chat_state_changed.emit(chat_id)
        if self._is_visible(chat_id):
            self._update_button_state(chat_id)

    @Slot(str, object)
    def _on_approval_needed(self, chat_id: str, event: object) -> None:
        """Show the approval bar for a pending ask-mode tool call.

        Args:
            chat_id: The chat awaiting approval.
            event: The ``tool_call`` event dict.
        """
        state = self.session.state(chat_id)
        info = cast(dict, event)
        state.pending_tool_info = info
        state.approval_text = f"Approve {info.get('name', '')}?"
        self._refresh_sidebar()
        if self._is_visible(chat_id):
            self._approval_text = state.approval_text
            self._set_approval_visible(True)
        self.chat_state_changed.emit(chat_id)

    @Slot(str)
    def _on_approval_cleared(self, chat_id: str) -> None:
        """Hide the approval bar once the pending tool call resolves.

        Args:
            chat_id: The chat whose approval resolved.
        """
        if not chat_id:
            return
        state = self.session.state(chat_id)
        state.pending_tool_info = None
        state.approval_text = ""
        if self._is_visible(chat_id):
            self._set_approval_visible(False)
        self.chat_state_changed.emit(chat_id)

    @Slot(str, int, int)
    def _on_token_usage(self, chat_id: str, input_tokens: int, output_cum: int) -> None:
        """Update a chat's true token counts.

        Args:
            chat_id: The chat whose usage updated.
            input_tokens: Context (input) token count.
            output_cum: Cumulative output token count.
        """
        state = self.session.state(chat_id)
        state.true_input_tokens = input_tokens
        state.true_output_cum = output_cum
        if self._is_visible(chat_id):
            self._update_token_bar(chat_id, state)

    @Slot(str, str, str)
    def _on_error(self, chat_id: str, brief: str, detail: str) -> None:
        """Record a generation error and toast the brief.

        Args:
            chat_id: The chat that errored.
            brief: UI-visible error message.
            detail: Log-visible error detail.
        """
        state = self.session.state(chat_id)
        state.has_error = True
        logger.error("Chat '%s' error: %s", chat_id, detail)
        if self._is_visible(chat_id):
            self.toast_requested.emit(brief, TOAST_ERROR)
        self.chat_state_changed.emit(chat_id)

    @Slot(str, int)
    def _on_message_count(self, chat_id: str, count: int) -> None:
        """Store a chat's current message count and refresh the sidebar.

        Args:
            chat_id: The chat that changed.
            count: The new message count.
        """
        state = self.session.state(chat_id)
        state.message_count = count
        self._refresh_sidebar()

    @Slot(str, str)
    def _on_compaction_ready(self, chat_id: str, summary: str) -> None:
        """Start a compacted chat once a worker produces a summary.

        Args:
            chat_id: The summarised chat id.
            summary: The summary text.
        """
        self._spawn(self._create_compacted_chat(chat_id, summary))

    @Slot(str, object)
    def _on_config_updated(self, chat_id: str, result: object) -> None:
        """Forward a worker's live-config result to interested controllers.

        Args:
            chat_id: The chat whose config changed.
            result: The ``update_skill_config`` result dict.
        """
        self.config_updated.emit(chat_id, result)

    # ------------------------------------------------------------------
    #  Compaction
    # ------------------------------------------------------------------

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
    #  Rendering: optimistic rows
    # ------------------------------------------------------------------

    def _append_user_message(self, chat_id: str, text: str) -> None:
        """Optimistically append a user message row to a chat's model.

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

        Args:
            chat_id: The chat to append to.
        """
        if not chat_id:
            return
        model = self.model_for(chat_id)
        model.append_item(build_waiting_item(), "w:pending")

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
        ctx = state.true_input_tokens if state else 0
        out = state.true_output_cum if state else 0
        self._set_token_counts(ctx, out)
        self.chat_tokens_changed.emit(chat_id)

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
        """Reflect a chat's busy state on the focused busy property.

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

    def _set_approval_visible(self, visible: bool) -> None:
        """Show or hide the approval bar.

        Args:
            visible: ``True`` to show, ``False`` to hide.
        """
        if self._approval_visible == visible:
            return
        self._approval_visible = visible
        self.approval_visibility_changed.emit(visible)

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
