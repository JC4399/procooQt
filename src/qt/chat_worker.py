"""``ChatWorker`` — one independent thread per chat.

Each worker owns an :class:`~src.chat.agent.Agent` and its rendering pipeline
inside a dedicated ``QThread`` that runs its own asyncio event loop.  The GUI
thread only sends commands and applies ready row updates, so chats stream and
render fully independently of one another.  Cross-thread traffic is one-way
each direction: commands arrive via ``loop.call_soon_threadsafe`` and results
are emitted as Qt signals queued back to the GUI thread.
"""

from __future__ import annotations

import asyncio
import json
import logging
from threading import Event as ThreadEvent, Lock
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Signal

from .chat_render import (
    ChatRenderer,
    RenderPlan,
    assistant_decision,
    build_context_snapshot,
    delete_bounds,
    normalize_content,
)

if TYPE_CHECKING:
    from ..app import ProcooApp
    from ..chat.agent import Agent

logger = logging.getLogger("procoo_qt")

#: Minimum seconds between in-place streaming body updates for one chat.
_STREAM_UPDATE_INTERVAL = 0.08


class ChatWorker(QThread):
    """Runs one chat's agent loop and rendering on a private thread.

    Signals:
        plan_ready: A full render plan (chat_id, :class:`RenderPlan`).
        stream_updated: In-place row updates (chat_id, list of ``(row, values)``).
        result_swap: Replace a pending tool-result card (chat_id, tool_id, item, key).
        turn_started: A generation began (chat_id, gen_id).
        turn_finished: A generation ended (chat_id, gen_id).
        approval_needed: An ask-mode tool awaits approval (chat_id, event).
        approval_cleared: The pending approval resolved (chat_id).
        token_usage: True API token counts (chat_id, input, output_cumulative).
        error: A generation error (chat_id, brief, detail).
        message_count: Current message count (chat_id, count).
        compaction_ready: The chat exceeded its limit and a summary is ready (chat_id, summary).
        config_updated: Live skill/tool config changed (chat_id, result dict).
    """

    plan_ready = Signal(str, object)
    stream_updated = Signal(str, object)
    result_swap = Signal(str, str, object, str)
    turn_started = Signal(str, int)
    turn_finished = Signal(str, int)
    approval_needed = Signal(str, object)
    approval_cleared = Signal(str)
    token_usage = Signal(str, int, int)
    error = Signal(str, str, str)
    message_count = Signal(str, int)
    compaction_ready = Signal(str, str)
    config_updated = Signal(str, object)

    def __init__(self, chat_id: str, agent: Agent, app: ProcooApp) -> None:
        """Initialise the worker.

        Args:
            chat_id: The chat id.
            agent: The live agent this worker owns.
            app: The backend application (used for persistence).
        """
        super().__init__()
        self.chat_id = chat_id
        self.agent = agent
        self._app = app
        self.renderer = ChatRenderer()
        self._banners: list[dict[str, Any]] = []
        self.visible = False
        self.is_busy = False
        self.has_error = False
        self.true_input_tokens = 0
        self.true_output_cum = 0
        self._last_count = 0
        self._last_rendered = 0
        self._tool_results: list[dict[str, Any]] = []
        self._run_task: asyncio.Task[Any] | None = None
        self._pump_task: asyncio.Task[Any] | None = None
        self._compact_task: asyncio.Task[Any] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = ThreadEvent()

        stored = app.chat_store.load_chat(chat_id) if app else None
        if stored:
            self.true_input_tokens = int(stored.get("true_input_tokens", 0) or 0)
            self.true_output_cum = int(stored.get("true_output_cum", 0) or 0)

    # ------------------------------------------------------------------
    #  Thread body
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Thread entry point: run the chat's asyncio loop forever."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._pump_task = loop.create_task(self._pump())
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            self._shutdown_loop()

    def _shutdown_loop(self) -> None:
        """Cancel remaining tasks and close the loop."""
        loop = self._loop
        if loop is None:
            return
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    async def _pump(self) -> None:
        """Drain the agent event queue and handle each event on this thread."""
        while True:
            event = await self.agent.event_queue.get()
            try:
                self._handle_event(event)
            except Exception:
                logger.exception("ChatWorker[%s] event handling failed", self.chat_id)

    # ------------------------------------------------------------------
    #  Command dispatch (called from the GUI thread)
    # ------------------------------------------------------------------

    def _post(self, callback: Any) -> None:
        """Schedule ``callback`` on the worker loop from the GUI thread."""
        if not self._ready.wait(timeout=5.0):
            logger.error("ChatWorker[%s] loop not ready", self.chat_id)
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(callback)

    def start_turn(self, message: str, gen_id: int) -> None:
        """Start one user turn.

        Args:
            message: The user message text.
            gen_id: GUI generation counter for stale-turn detection.
        """
        self._post(lambda: self._do_start_turn(message, gen_id))

    def confirm_approval(self, tool_id: str) -> None:
        """Approve a pending tool call."""
        self._post(lambda: asyncio.ensure_future(self.agent.approve_tool(tool_id)))

    def deny_approval(self, tool_id: str, reason: str) -> None:
        """Deny a pending tool call."""
        self._post(lambda: asyncio.ensure_future(self.agent.deny_tool(tool_id, reason)))

    def cancel_turn(self) -> None:
        """Cancel the running turn."""
        self._post(self._do_cancel)

    def set_model(self, model: dict) -> None:
        """Replace the agent's model for subsequent turns."""
        self._post(lambda: self.agent.set_model(model))

    def update_config(
        self,
        primary: list[dict],
        secondary: list[dict],
        tools: list[dict],
        tool_config: dict[str, str],
    ) -> None:
        """Push new skill/tool configuration and emit the result."""
        self._post(lambda: self._do_update_config(primary, secondary, tools, tool_config))

    def append_banner(self, banner: dict[str, Any]) -> None:
        """Append a delta context banner and rebuild."""
        self._post(lambda: self._do_append_banner(banner))

    def delete_turn(self, msg_index: int) -> None:
        """Delete the message object behind a card."""
        self._post(lambda: self._do_delete_turn(msg_index))

    def regenerate(self, gen_id: int) -> None:
        """Trim the last user turn and re-run it."""
        self._post(lambda: self._do_regenerate(gen_id))

    def regenerate_from(self, msg_index: int, gen_id: int) -> None:
        """Trim to before a user message and re-run from it."""
        self._post(lambda: self._do_regenerate_from(msg_index, gen_id))

    def append_message(self, message: dict) -> None:
        """Append a raw message (editor context injection)."""
        self._post(lambda: self.agent.messages.append(message))

    def invalidate_cache(self) -> None:
        """Drop cached rendered items and rebuild."""
        self._post(self._do_invalidate)

    def set_visible(self, visible: bool) -> None:
        """Record whether the chat is shown; rebuild on becoming visible."""
        self._post(lambda: self._do_set_visible(visible))

    def request_rebuild(self) -> None:
        """Emit a fresh full render plan."""
        self._post(self._emit_plan)

    def request_persist(self) -> None:
        """Persist the chat to disk."""
        self._post(self._do_persist)

    def stop(self) -> None:
        """Stop the loop and join the thread."""
        if not self._ready.wait(timeout=5.0):
            return
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)
        self.wait(5000)

    # ------------------------------------------------------------------
    #  Command implementations (worker thread)
    # ------------------------------------------------------------------

    def _do_start_turn(self, message: str, gen_id: int) -> None:
        self.is_busy = True
        self.has_error = False
        self._last_count = 0
        self._last_rendered = 0
        self.turn_started.emit(self.chat_id, gen_id)
        self._run_task = asyncio.ensure_future(self._run_turn(message, gen_id))

    async def _run_turn(self, message: str, gen_id: int) -> None:
        try:
            await self.agent.run(message)
        except Exception:
            logger.exception("ChatWorker[%s] run failed", self.chat_id)
        finally:
            self.is_busy = False
            self._finalize()
            self.turn_finished.emit(self.chat_id, gen_id)

    def _do_cancel(self) -> None:
        if self._run_task is not None and not self._run_task.done():
            self._run_task.cancel()

    def _do_update_config(
        self,
        primary: list[dict],
        secondary: list[dict],
        tools: list[dict],
        tool_config: dict[str, str],
    ) -> None:
        try:
            result = self.agent.update_skill_config(primary, secondary, tools, tool_config)
        except Exception:
            logger.exception("ChatWorker[%s] config update failed", self.chat_id)
            return
        self.config_updated.emit(self.chat_id, result)

    def _do_append_banner(self, banner: dict[str, Any]) -> None:
        if self._banners and self._banners[-1].get("is_delta"):
            self._banners.pop()
        self._banners.append(banner)
        if self.visible:
            self._emit_plan()

    def _do_delete_turn(self, msg_index: int) -> None:
        messages = self.agent.messages
        if not 0 <= msg_index < len(messages):
            return
        start, end = delete_bounds(messages, msg_index)
        del messages[start:end]
        self.agent._current_assistant_msg = None
        self.renderer.invalidate_cache()
        self._do_persist()
        self.message_count.emit(self.chat_id, len(messages))
        self._last_rendered = 0
        self._emit_plan()

    def _do_regenerate(self, gen_id: int) -> None:
        messages = self.agent.messages
        idx = next(
            (i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "user"),
            None,
        )
        if idx is None:
            return
        text = normalize_content(messages[idx].get("content", ""))
        self._trim_and_restart(idx, text, gen_id)

    def _do_regenerate_from(self, msg_index: int, gen_id: int) -> None:
        messages = self.agent.messages
        if not 0 <= msg_index < len(messages) or messages[msg_index].get("role") != "user":
            return
        text = normalize_content(messages[msg_index].get("content", ""))
        self._trim_and_restart(msg_index, text, gen_id)

    def _trim_and_restart(self, keep_index: int, text: str, gen_id: int) -> None:
        del self.agent.messages[keep_index:]
        self.agent._current_assistant_msg = None
        self.renderer.invalidate_cache()
        self._do_persist()
        self.message_count.emit(self.chat_id, len(self.agent.messages))
        self._last_rendered = 0
        self._emit_plan()
        self._do_start_turn(text, gen_id)

    def _do_invalidate(self) -> None:
        self.renderer.invalidate_cache()
        self._last_rendered = 0
        self._emit_plan()

    def _do_set_visible(self, visible: bool) -> None:
        if self.visible == visible:
            return
        self.visible = visible
        if visible:
            self._last_rendered = 0
            self._emit_plan()

    # ------------------------------------------------------------------
    #  Event handling (worker thread)
    # ------------------------------------------------------------------

    def _handle_event(self, event: dict) -> None:
        """Port of the GUI event consume loop, run entirely on this thread."""
        etype = event.get("type", "")
        if etype == "tool_call" and event.get("mode", "ask") == "ask":
            self.approval_needed.emit(self.chat_id, event)
        elif etype == "tool_result":
            self._tool_results.append(event)
            self.approval_cleared.emit(self.chat_id)
        elif etype == "token_usage":
            self.true_input_tokens = event.get("input", 0)
            self.true_output_cum = event.get("output_cumulative", 0)
            self.token_usage.emit(self.chat_id, self.true_input_tokens, self.true_output_cum)
        elif etype == "error":
            self.has_error = True
            brief = event.get("brief", event.get("message", "Unknown error"))
            self.error.emit(self.chat_id, brief, event.get("detail", ""))
            return
        elif etype == "done":
            return

        msg_count = len(self.agent.messages)
        if msg_count != self._last_count:
            self._last_count = msg_count
            self.message_count.emit(self.chat_id, msg_count)
        if self.visible:
            self._render_active(event, msg_count)

    def _render_active(self, event: dict, msg_count: int) -> None:
        if msg_count != self._last_rendered:
            if event.get("type", "") == "tool_result":
                self._swap_pending_result(event)
            else:
                self._emit_plan()
            self._last_rendered = msg_count
            return
        messages = self.agent.messages
        if messages and messages[-1].get("role") != "assistant":
            self._emit_plan()
        else:
            self._update_live()

    def _swap_pending_result(self, event: dict) -> None:
        messages = self.agent.messages
        msg_index = len(messages) - 1 if messages else -1
        item, key = self.renderer.build_result_replacement(
            event.get("name", ""), event.get("content", ""), msg_index
        )
        self.result_swap.emit(self.chat_id, event.get("id", ""), item, key)

    def _update_live(self) -> None:
        messages = self.agent.messages
        if not messages or messages[-1].get("role") != "assistant":
            return
        last_msg = messages[-1]
        decision = assistant_decision(last_msg)
        thinking_text = decision["thinking_text"]
        content_text = decision["content_text"]
        state = self.renderer.state

        thinking_changed = thinking_text != state.last_rendered_thinking_text
        content_changed = content_text != state.last_rendered_message_text
        tool_calls_changed = len(last_msg.get("tool_calls", [])) != state.last_rendered_tool_calls
        tool_results_changed = len(self._tool_results) != state.last_rendered_tool_results
        streaming_tcs = last_msg.get("_streaming_tool_calls")
        streaming_tc_json = json.dumps(streaming_tcs) if streaming_tcs else ""
        streaming_tc_changed = (
            bool(streaming_tcs) and streaming_tc_json != state.last_rendered_streaming_tc_json
        )
        streaming_tc_needs_rebuild = streaming_tc_changed and not state.tool_call_indices
        now = time.monotonic()

        if tool_calls_changed or tool_results_changed or streaming_tc_needs_rebuild:
            state.last_rebuild_time = now
            self._emit_plan()
            self._track_rendered()
            return
        missing_pending = (
            thinking_text and not decision["thinking_done"] and state.thinking.item_index is None
        ) or (content_text and not decision["response_done"] and state.response.item_index is None)
        if missing_pending:
            state.last_rebuild_time = now
            self._emit_plan()
            self._track_rendered()
            return
        content_only = thinking_changed or content_changed
        streaming_active = streaming_tc_changed and bool(state.tool_call_indices)
        if not (content_only or streaming_active):
            return
        if now - state.last_content_update_time < _STREAM_UPDATE_INTERVAL:
            self._track_rendered()
            return
        state.last_content_update_time = now
        updates = self.renderer.build_stream_update(
            thinking_text, content_text, streaming_tcs, thinking_changed, content_changed
        )
        if updates:
            self.stream_updated.emit(self.chat_id, updates)
        self._track_rendered()

    def _track_rendered(self) -> None:
        state = self.renderer.state
        messages = self.agent.messages
        if messages and messages[-1].get("role") == "assistant":
            last = messages[-1]
            state.last_rendered_thinking_text = last.get("reasoning_content", "")
            state.last_rendered_message_text = last.get("content", "") or ""
            state.last_rendered_tool_calls = len(last.get("tool_calls", []))
            state.last_rendered_tool_results = len(self._tool_results)
            streaming_tcs = last.get("_streaming_tool_calls")
            state.last_rendered_streaming_tc_json = (
                json.dumps(streaming_tcs) if streaming_tcs else ""
            )

    # ------------------------------------------------------------------
    #  Plan emission
    # ------------------------------------------------------------------

    def _emit_plan(self) -> None:
        """Build and emit a full render plan for the current messages."""
        if self._loop is None:
            return
        snapshot = build_context_snapshot(self.agent)
        plan: RenderPlan = self.renderer.build_plan(
            self.agent.messages, snapshot, self._banners, self.is_busy
        )
        self.plan_ready.emit(self.chat_id, plan)

    # ------------------------------------------------------------------
    #  Finalize / persistence
    # ------------------------------------------------------------------

    def _finalize(self) -> None:
        self.is_busy = False
        if self.visible:
            self._last_rendered = len(self.agent.messages)
            self._emit_plan()
        self._do_persist()
        self.message_count.emit(self.chat_id, len(self.agent.messages))
        self.approval_cleared.emit(self.chat_id)
        self.renderer.reset_turn()
        self._tool_results.clear()
        if self.agent.check_limit_exceeded() is not None:
            self._compact_task = asyncio.ensure_future(self._compact())

    async def _compact(self) -> None:
        summary = await self.agent.summarize()
        if summary:
            self.compaction_ready.emit(self.chat_id, summary)

    def _do_persist(self) -> None:
        if self._app is None:
            return
        stored = self._app.chat_store.load_chat(self.chat_id)
        if not stored:
            return
        stored["messages"] = list(self.agent.messages)
        stored["message_count"] = len(self.agent.messages)
        stored["context_snapshot"] = build_context_snapshot(self.agent)
        stored["true_input_tokens"] = self.true_input_tokens
        stored["true_output_cum"] = self.true_output_cum
        self._app.chat_store.save_chat(self.chat_id, stored)


# ------------------------------------------------------------------
#  Registry
# ------------------------------------------------------------------

_workers: dict[str, ChatWorker] = {}
_workers_lock = Lock()


def get_worker(chat_id: str) -> ChatWorker | None:
    """Return the live worker for a chat, or ``None``.

    Args:
        chat_id: The chat id.

    Returns:
        The worker, if one is running.
    """
    with _workers_lock:
        return _workers.get(chat_id)


def ensure_worker(chat_id: str, agent: Agent, app: ProcooApp) -> ChatWorker:
    """Return the worker for a chat, creating and starting it on demand.

    Args:
        chat_id: The chat id.
        agent: The live agent the worker should own.
        app: The backend application.

    Returns:
        The running worker.
    """
    with _workers_lock:
        worker = _workers.get(chat_id)
        if worker is not None and worker.agent is agent and worker.isRunning():
            return worker
        if worker is not None:
            worker.stop()
        worker = ChatWorker(chat_id, agent, app)
        _workers[chat_id] = worker
    worker.start()
    return worker


def remove_worker(chat_id: str) -> None:
    """Stop and drop a chat's worker.

    Args:
        chat_id: The chat id.
    """
    with _workers_lock:
        worker = _workers.pop(chat_id, None)
    if worker is not None:
        worker.stop()


def stop_all_workers() -> None:
    """Stop every worker (application shutdown)."""
    with _workers_lock:
        workers = list(_workers.values())
        _workers.clear()
    for worker in workers:
        worker.stop()
