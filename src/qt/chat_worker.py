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
from threading import Event as ThreadEvent, Lock, Thread
import time
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QThread, Signal

from .chat_items import thinking_body
from .chat_render import (
    ChatRenderer,
    RenderPlan,
    assistant_decision,
    build_context_snapshot,
    delete_bounds,
    normalize_content,
)
from .context_banner import build_skill_update_sections
from .markdown import render_markdown
from .qt_roles import ChatRole

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

    # ------------------------------------------------------------------
    #  Thread body
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Thread entry point: run the chat's asyncio loop forever."""
        self._load_stored_state()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._pump_task = loop.create_task(self._pump())
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            self._shutdown_loop()

    def _load_stored_state(self) -> None:
        """Load persisted token counts and banners on the worker thread."""
        stored = self._app.chat_store.load_chat(self.chat_id) if self._app else None
        if not stored:
            return
        self.true_input_tokens = int(stored.get("true_input_tokens", 0) or 0)
        self.true_output_cum = int(stored.get("true_output_cum", 0) or 0)
        self._banners = self._load_banners(stored.get("context_banners", []))

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
        activated: list[dict],
        tools: list[dict],
        tool_config: dict[str, str],
    ) -> None:
        """Push new skill/tool configuration and emit the result."""
        self._post(lambda: self._do_update_config(activated, tools, tool_config))

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

    def request_prewarm_plan(self) -> None:
        """Emit a full plan for pre-warming.

        The plan is built on this chat's worker thread, so it never blocks the
        GUI loop.
        """
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
        self._commit_pending_banners()
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
            try:
                self._finalize()
            except Exception:
                logger.exception("ChatWorker[%s] finalize failed", self.chat_id)
            self.turn_finished.emit(self.chat_id, gen_id)

    def _do_cancel(self) -> None:
        if self._run_task is not None and not self._run_task.done():
            self._run_task.cancel()

    def _do_update_config(
        self,
        activated: list[dict],
        tools: list[dict],
        tool_config: dict[str, str],
    ) -> None:
        try:
            result = self.agent.update_skill_config(activated, tools, tool_config)
        except Exception:
            logger.exception("ChatWorker[%s] config update failed", self.chat_id)
            return
        self._sync_pending_banner(result)
        self.config_updated.emit(self.chat_id, result)

    def _do_delete_turn(self, msg_index: int) -> None:
        messages = self.agent.messages
        if not 0 <= msg_index < len(messages):
            return
        start, end = delete_bounds(messages, msg_index)
        del messages[start:end]
        self._prune_banners_after_delete(start, end)
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
        self._prune_banners_after_trim(keep_index)
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
    #  Banner lifecycle (worker thread)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_banners(raw: object) -> list[dict[str, Any]]:
        """Normalise persisted banners loaded from the chat store.

        Args:
            raw: The stored ``context_banners`` value.

        Returns:
            A list of banner dicts with integer anchors and ``pending=False``.
        """
        if not isinstance(raw, list):
            return []
        banners: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            banner = cast(dict[str, Any], item)
            banner["anchor"] = int(banner.get("anchor", 0) or 0)
            banner["pending"] = False
            banners.append(banner)
        return banners

    def _sync_pending_banner(self, result: dict[str, Any]) -> None:
        """Create, update, or remove the not-yet-sent skill-update banner.

        The banner body is the exact system-message text that ``Agent.run`` will
        inject before the next user message. Tool-only or mode-only changes
        produce no text, so no banner is created for them.

        Args:
            result: The ``update_skill_config`` result dict.
        """
        text = str(result.get("pending_sys_message", "") or "").strip()
        previous = [banner for banner in self._banners if banner.get("pending")]
        self._banners = [banner for banner in self._banners if not banner.get("pending")]
        if text:
            self._banners.append(
                {
                    "type": "delta",
                    "title": "Skill Update",
                    "sections": build_skill_update_sections(text),
                    "is_delta": True,
                    "anchor": len(self.agent.messages),
                    "pending": True,
                }
            )
        if (previous or text) and self.visible:
            self._emit_plan()

    def _commit_pending_banners(self) -> None:
        """Mark pending banners as committed when their system message is sent."""
        for banner in self._banners:
            if banner.get("pending"):
                banner["pending"] = False

    def _prune_banners_after_delete(self, start: int, end: int) -> None:
        """Drop or shift banners after a ``[start, end)`` message deletion.

        Args:
            start: First deleted message index.
            end: One past the last deleted message index.
        """
        removed = end - start
        kept: list[dict[str, Any]] = []
        for banner in self._banners:
            anchor = int(banner.get("anchor", 0) or 0)
            if start <= anchor < end:
                continue
            if anchor >= end:
                banner["anchor"] = anchor - removed
            kept.append(banner)
        self._banners = kept

    def _prune_banners_after_trim(self, keep_index: int) -> None:
        """Drop banners anchored after a message-list trim point.

        Args:
            keep_index: First removed message index.
        """
        self._banners = [
            banner for banner in self._banners if int(banner.get("anchor", 0) or 0) <= keep_index
        ]

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
            # Do not mark the pending text as rendered: it was never emitted, so
            # the next tick (or the finalize flush) must still re-detect it.
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

    def _flush_final_body(self) -> None:
        """Push the complete body for still-pending streaming cards.

        Streaming sends a frozen prefix plus a live tail, and the live path is
        throttled, so the final tick can be dropped. Writing the whole final text
        into ``BODY_HTML`` and clearing the tail guarantees the card is complete
        before the per-turn render state is reset, independent of the rebuild.
        """
        messages = self.agent.messages
        if not messages or messages[-1].get("role") != "assistant":
            return
        decision = assistant_decision(messages[-1])
        state = self.renderer.state
        updates: list[tuple[int, dict[int, object]]] = []
        thinking_text = decision["thinking_text"]
        if thinking_text and state.thinking.item_index is not None:
            updates.append(
                (
                    state.thinking.item_index,
                    {
                        int(ChatRole.BODY_HTML): thinking_body(thinking_text),
                        int(ChatRole.BODY_TAIL_HTML): "",
                    },
                )
            )
        content_text = decision["content_text"]
        if content_text and state.response.item_index is not None:
            updates.append(
                (
                    state.response.item_index,
                    {
                        int(ChatRole.BODY_HTML): render_markdown(content_text),
                        int(ChatRole.BODY_TAIL_HTML): "",
                    },
                )
            )
        if updates:
            self.stream_updated.emit(self.chat_id, updates)

    def _finalize(self) -> None:
        """Finalize a turn: flush the body, rebuild, persist, and reset.

        The final body flush runs before the per-turn state is reset so the
        streaming cards are guaranteed to show the whole response even if the
        non-incremental rebuild is dropped. Each step is independently guarded so
        one failure cannot leave a card truncated or the chat stuck busy.
        """
        self.is_busy = False
        try:
            self._flush_final_body()
        except Exception:
            logger.exception("ChatWorker[%s] final body flush failed", self.chat_id)
        self._last_rendered = len(self.agent.messages)
        try:
            self._emit_plan()
        except Exception:
            logger.exception("ChatWorker[%s] final plan failed", self.chat_id)
        try:
            self._do_persist()
        except Exception:
            logger.exception("ChatWorker[%s] persist failed", self.chat_id)
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
        stored["context_banners"] = [
            banner for banner in self._banners if not banner.get("pending")
        ]
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


def remove_worker_async(chat_id: str) -> None:
    """Detach a worker and stop its thread without blocking the caller.

    Used when reclaiming an evicted chat on the GUI thread. The worker may still
    be finishing a render, so waiting for its thread here would freeze the UI.

    Args:
        chat_id: The chat id.
    """
    with _workers_lock:
        worker = _workers.pop(chat_id, None)
    if worker is not None:
        Thread(target=worker.stop, daemon=True).start()


def stop_all_workers() -> None:
    """Stop every worker (application shutdown)."""
    with _workers_lock:
        workers = list(_workers.values())
        _workers.clear()
    for worker in workers:
        worker.stop()
