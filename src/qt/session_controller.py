"""``SessionController`` — session sidebar, chat lifecycle, and persistence.

Owns the session/chat list model and the per-chat :class:`ChatState` registry.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..chat.manager import chat_manager
from ..chat.store import DEFAULT_SESSION_NAME
from ..util.error.types import ChatError
from .chat_panel_model import ChatPanelModel
from .chat_state import ChatState
from .error_handler import TOAST_ERROR, TOAST_WARNING
from .models.session_menu_model import SessionMenuModel
from .theme import (
    COLOR_CHAT_EMPTY,
    COLOR_CHAT_ERROR,
    COLOR_CHAT_FINISHED,
    COLOR_CHAT_RUNNING,
    COLOR_CHAT_WAITING,
)

if TYPE_CHECKING:
    from ..app import ProcooApp
    from .chat_controller import ChatController
    from .session_bus import SessionBus

logger = logging.getLogger("procoo_qt")


class ChatStatus:
    """String constants for chat display statuses."""

    EMPTY = "empty"
    RUNNING = "running"
    WAITING = "waiting"
    FINISHED = "finished"
    ERROR = "error"


_STATUS_COLORS: dict[str, str] = {
    ChatStatus.EMPTY: COLOR_CHAT_EMPTY,
    ChatStatus.FINISHED: COLOR_CHAT_FINISHED,
    ChatStatus.WAITING: COLOR_CHAT_WAITING,
    ChatStatus.RUNNING: COLOR_CHAT_RUNNING,
    ChatStatus.ERROR: COLOR_CHAT_ERROR,
}


class SessionController(QObject):
    """Session group, chat creation/switching/deletion, and persistence controller."""

    sessions_changed = Signal()
    tabs_changed = Signal()
    panels_changed = Signal()
    active_chat_changed = Signal(str)
    active_session_name_changed = Signal()
    chat_switch_started = Signal(str)
    toast_requested = Signal(str, str)
    new_session_requested = Signal()
    models_changed = Signal()

    if TYPE_CHECKING:
        app: ProcooApp
        chat: ChatController
        _bus: SessionBus
        _session_menu_model: SessionMenuModel
        _states: dict[str, ChatState]
        _chats_by_session: dict[str, list[str]]
        _enriched: dict[str, dict[str, Any]]
        _panels: list[dict[str, Any]]
        _panel_models: list[ChatPanelModel]
        _tasks: set[asyncio.Task[Any]]
        active_chat_id: str | None
        active_session_name: str | None
        chat_ids: list[str]

        def _get_or_create_state(self, chat_id: str) -> ChatState: ...
        def _save_current_chat_for(self, chat_id: str) -> None: ...
        def _open_chat(self, chat_id: str) -> None: ...

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(
        self, app: ProcooApp, bus: SessionBus, parent: QObject | None = None
    ) -> None:
        """Initialise the session controller.

        Args:
            app: The top-level application holding backend subsystems.
            bus: The shared session-change broadcast hub.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._bus = bus

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the workspace panels, session menu, and per-chat state registry."""
        self._session_menu_model = SessionMenuModel(self)
        self._states = {}
        self._chats_by_session = {}
        self._enriched = {}
        self._panels = [{"chat_ids": [], "active_chat_id": ""}]
        self._panel_models = []
        self._tasks = set()
        self.active_chat_id = None
        self.active_session_name = None
        self.chat_ids = []
        self._refresh_model()
        self._bus.sessions_changed.connect(self.refresh_sessions)

    # ------------------------------------------------------------------
    #  Slot: Refresh sessions
    # ------------------------------------------------------------------

    @Slot()
    def refresh_sessions(self) -> None:
        """Reload the session menu model from disk.

        Connected to :class:`~src.qt.session_bus.SessionBus` so every open
        window's title bar reflects a session created or deleted elsewhere.
        Runs the disk scan off the GUI thread.
        """
        self._spawn(self.refresh_model_async())

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(int, notify=panels_changed)
    def panelCount(self) -> int:  # noqa: N802
        """Return the number of visible workspace panels.

        Returns:
            The panel count exposed to QML as ``session.panelCount``.
        """
        return len(self._panels)

    @Slot(int, result=QObject)
    def panelAt(self, index: int) -> QObject:  # noqa: N802
        """Return the panel view model at an index, creating it on demand.

        Args:
            index: The panel index.

        Returns:
            The panel's :class:`ChatPanelModel`.
        """
        while len(self._panel_models) <= index:
            self._panel_models.append(ChatPanelModel(len(self._panel_models), self))
        return self._panel_models[index]

    @Property(QObject, notify=sessions_changed)
    def sessionMenuModel(self) -> SessionMenuModel:  # noqa: N802
        """Return the title-bar session menu model.

        Returns:
            The model exposed to QML as ``session.sessionMenuModel``.
        """
        return self._session_menu_model

    @Property(str, notify=active_session_name_changed)
    def activeSessionName(self) -> str:  # noqa: N802
        """Return the active session name.

        Returns:
            The active session name, or an empty string.
        """
        return self.active_session_name or ""

    @Property(list, notify=models_changed)
    def modelNames(self) -> list[str]:  # noqa: N802
        """Return the configured LLM model names.

        Returns:
            The model names exposed to QML as ``session.modelNames``.
        """
        return self.app.config.llm_models

    # ------------------------------------------------------------------
    #  State
    # ------------------------------------------------------------------

    def state(self, chat_id: str) -> ChatState:
        """Return the state for a chat, creating it on demand.

        Args:
            chat_id: The chat id.

        Returns:
            The chat's UI state.
        """
        if chat_id not in self._states:
            self._states[chat_id] = ChatState(chat_id)
        return self._states[chat_id]

    def _get_or_create_state(self, chat_id: str) -> ChatState:
        """Return the state for a chat, creating it on demand.

        Args:
            chat_id: The chat id.

        Returns:
            The chat's UI state.
        """
        return self.state(chat_id)

    # ------------------------------------------------------------------
    #  Slot: Start
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Ensure a session exists and open its workspace panels."""
        self._emit_validation_issues()
        self.active_session_name = self.app.chat_store.ensure_default_session()
        self.active_session_name_changed.emit()
        self._refresh_model()
        self._reconcile_panels(self.active_session_name)
        self._sync_panels()
        self._open_session_panels()

    # ------------------------------------------------------------------
    #  Slot: New chat
    # ------------------------------------------------------------------

    @Slot(int)
    def _handle_new_chat(self, panel_index: int) -> None:
        """Create a new chat and open it as a tab in a panel.

        The new chat inherits the panel's current chat's skill/tool config and
        model, so a fresh chat continues the last working setup.

        Args:
            panel_index: The panel to add the chat to.
        """
        if not (0 <= panel_index < len(self._panels)):
            panel_index = 0
        source_chat_id = self._panels[panel_index]["active_chat_id"]
        chat_id = self._generate_unique_chat_id()
        self._create_stored_chat(chat_id, source_chat_id=source_chat_id)
        self._panels[panel_index]["chat_ids"].append(chat_id)
        self._panels[panel_index]["active_chat_id"] = chat_id
        self._refresh_model()
        self._save_layout()
        self._open_chat(chat_id)

    # ------------------------------------------------------------------
    #  Slot: Ensure chat
    # ------------------------------------------------------------------

    @Slot(int)
    def ensure_chat(self, panel_index: int = 0) -> None:
        """Create a chat in a panel when the session has none.

        Used so a freshly created session (e.g. from the control server) opens
        ready to use, with an active chat backing the per-chat skill/model dock.

        Args:
            panel_index: The panel to create the chat in.
        """
        session_chats = self._chats_by_session.get(self.active_session_name or "", [])
        if session_chats:
            return
        self._handle_new_chat(panel_index)

    # ------------------------------------------------------------------
    #  Slot: Panel tab activate
    # ------------------------------------------------------------------

    @Slot(int, str)
    def _handle_panel_activate(self, panel_index: int, chat_id: str) -> None:
        """Activate a chat tab within a panel.

        Args:
            panel_index: The panel whose tab was clicked.
            chat_id: The chat to activate.
        """
        if not (0 <= panel_index < len(self._panels)) or not chat_id:
            return
        if self._panels[panel_index]["active_chat_id"] == chat_id:
            return
        self._panels[panel_index]["active_chat_id"] = chat_id
        self._save_layout()
        self._sync_panels()
        self._open_chat(chat_id)

    # ------------------------------------------------------------------
    #  Slot: Move / split chat
    # ------------------------------------------------------------------

    @Slot(str, int)
    def _handle_move_chat(self, chat_id: str, target_index: int) -> None:
        """Move a chat into another panel's tab bar.

        Args:
            chat_id: The dragged chat id.
            target_index: The panel to move the chat into.
        """
        if not chat_id or not (0 <= target_index < len(self._panels)):
            return
        target = self._panels[target_index]
        if chat_id in target["chat_ids"]:
            return
        self._remove_chat_from_panels(chat_id)
        if target in self._panels:
            target["chat_ids"].append(chat_id)
            target["active_chat_id"] = chat_id
        else:
            self._panels.append({"chat_ids": [chat_id], "active_chat_id": chat_id})
        self._finalize_panel_change()
        self._open_chat(chat_id)

    @Slot(str, int, str)
    def _handle_split(self, chat_id: str, target_index: int, side: str) -> None:
        """Split a panel, moving a chat into a new adjacent panel.

        The target panel is always kept (even when the dragged chat was its only
        tab), so a drop on a panel half always yields one more visible panel.
        Other panels that become empty are dropped.

        Args:
            chat_id: The dragged chat id.
            target_index: The panel being split.
            side: ``"left"`` or ``"right"`` for the new panel position.
        """
        if not chat_id or not (0 <= target_index < len(self._panels)):
            return
        if len(self._panels) >= 4:
            return
        target = self._panels[target_index]
        for panel in self._panels:
            if chat_id in panel["chat_ids"]:
                panel["chat_ids"].remove(chat_id)
                if panel["active_chat_id"] == chat_id:
                    panel["active_chat_id"] = panel["chat_ids"][0] if panel["chat_ids"] else ""
        self._panels = [p for p in self._panels if p["chat_ids"] or p is target]
        target_pos = self._panels.index(target)
        position = target_pos if side == "left" else target_pos + 1
        position = max(0, min(position, len(self._panels)))
        self._panels.insert(position, {"chat_ids": [chat_id], "active_chat_id": chat_id})
        self._finalize_panel_change()
        self._open_chat(chat_id)

    def _remove_chat_from_panels(self, chat_id: str) -> None:
        """Remove a chat from every panel, dropping panels left empty.

        The caller is responsible for ensuring at least one panel remains.

        Args:
            chat_id: The chat id to remove.
        """
        for panel in self._panels:
            if chat_id in panel["chat_ids"]:
                panel["chat_ids"].remove(chat_id)
                if panel["active_chat_id"] == chat_id:
                    panel["active_chat_id"] = panel["chat_ids"][0] if panel["chat_ids"] else ""
        self._panels = [p for p in self._panels if p["chat_ids"]]

    def _ensure_panel_exists(self) -> None:
        """Guarantee at least one (possibly empty) panel remains."""
        if not self._panels:
            self._panels = [{"chat_ids": [], "active_chat_id": ""}]

    def _finalize_panel_change(self) -> None:
        """Sync panel models and persist the layout after a panel mutation."""
        self._sync_panels()
        self._save_layout()

    # ------------------------------------------------------------------
    #  Slot: Delete chat
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_delete_chat(self, chat_id: str) -> None:
        """Delete a chat, removing it from its panel.

        Args:
            chat_id: The chat id to delete.
        """
        if not chat_id:
            return
        self._delete_chat_by_id(chat_id)

    # ------------------------------------------------------------------
    #  Slot: New session
    # ------------------------------------------------------------------

    @Slot()
    def _handle_new_session(self) -> None:
        """Request that QML open the new-session dialog."""
        self.new_session_requested.emit()

    # ------------------------------------------------------------------
    #  Slot: Create session
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_create_session(self, name: str) -> None:
        """Create a session and switch to it.

        Args:
            name: The session name entered in the dialog.
        """
        cleaned = (name or "").strip()
        if not cleaned:
            self.toast_requested.emit("Please enter a session name.", TOAST_ERROR)
            return
        try:
            self.app.chat_store.create_session(cleaned)
        except ValueError as error:
            self.toast_requested.emit(str(error), TOAST_ERROR)
            return
        self._handle_switch_session(cleaned)
        self._bus.sessions_changed.emit()

    # ------------------------------------------------------------------
    #  Slot: Switch session
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_switch_session(self, name: str) -> None:
        """Activate a session and rebuild its workspace panels.

        Args:
            name: The session name to activate.
        """
        if not name or name == self.active_session_name:
            return
        self._activate_session(name)

    # ------------------------------------------------------------------
    #  Slot: Open session (new window)
    # ------------------------------------------------------------------

    @Slot(str)
    def open_session(self, name: str) -> None:
        """Activate a session unconditionally and rebuild its workspace panels.

        Used when a fresh window is created for a session: unlike
        :meth:`_handle_switch_session`, it does not skip the activation when the
        name matches the (empty) current selection.

        Args:
            name: The session name to activate.
        """
        if not name:
            return
        self._activate_session(name)

    def _activate_session(self, name: str) -> None:
        """Set the active session and rebuild every panel for it.

        Args:
            name: The session name to activate.
        """
        self.active_session_name = name
        self.active_session_name_changed.emit()
        self.active_chat_id = None
        self._refresh_model()
        self._reconcile_panels(name)
        self._sync_panels()
        self._open_session_panels()

    # ------------------------------------------------------------------
    #  Slot: Delete session
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_delete_session(self, name: str) -> None:
        """Delete a session and all its chats.

        Args:
            name: The session name to delete.
        """
        if not name:
            return
        try:
            deleted_ids = self.app.chat_store.delete_session(name)
        except ValueError as error:
            self.toast_requested.emit(str(error), TOAST_ERROR)
            return
        for chat_id in deleted_ids:
            self._forget_chat(chat_id)
        if name == self.active_session_name:
            self.active_session_name = self.app.chat_store.ensure_default_session()
            self.active_session_name_changed.emit()
            self.active_chat_id = None
            self._refresh_model()
            self._reconcile_panels(self.active_session_name)
            self._sync_panels()
            self._open_session_panels()
            self._bus.sessions_changed.emit()
            return
        self._refresh_model()
        self._bus.sessions_changed.emit()

    # ------------------------------------------------------------------
    #  Slot: Status color
    # ------------------------------------------------------------------

    @Slot(str, result=str)
    def statusColor(self, status: str) -> str:  # noqa: N802
        """Return the theme color for a chat status.

        Args:
            status: One of the :class:`ChatStatus` strings.

        Returns:
            A hex color string suitable for a QML dot.
        """
        return _STATUS_COLORS.get(status, COLOR_CHAT_EMPTY)

    # ------------------------------------------------------------------
    #  Slot: Model selection
    # ------------------------------------------------------------------

    @Slot(str, result=str)
    def modelNameFor(self, chat_id: str) -> str:  # noqa: N802
        """Return the LLM model name selected for a chat.

        Args:
            chat_id: The chat id (empty falls back to the config default).

        Returns:
            The chat's model name, or the config default when unset.
        """
        default = self.app.config.llm_model_name
        if not chat_id:
            return default
        return self.state(chat_id).model_name or default

    @Slot(str, str)
    def _handle_model_changed(self, chat_id: str, model_name: str) -> None:
        """Set the LLM model for a chat and apply it immediately.

        Persists the choice to the chat record, updates the chat's UI state,
        swaps the live agent's model (when one exists), and refreshes the panel.

        Args:
            chat_id: The chat whose model changed.
            model_name: The newly selected model name.
        """
        if not chat_id or not model_name:
            return
        if model_name not in self.app.config.llm_models:
            self.toast_requested.emit(f"Unknown model: {model_name}", TOAST_ERROR)
            return
        state = self.state(chat_id)
        state.model_name = model_name
        stored = self.app.chat_store.load_chat(chat_id)
        if stored:
            stored["model_name"] = model_name
            self.app.chat_store.save_chat(chat_id, stored)
        live = chat_manager.get_chat(chat_id)
        if live is not None:
            live.set_model(self.app.config.llm_config(model_name))
        self.refresh_chat_panels(chat_id)

    # ------------------------------------------------------------------
    #  Session model
    # ------------------------------------------------------------------

    def _refresh_model(self) -> None:
        """Reload chat summaries and sessions into the list model."""
        enriched, sessions = self._collect_summaries()
        self._apply_summaries(enriched, sessions)

    async def refresh_model_async(self) -> None:
        """Reload the sidebar model with the disk scan off the GUI thread.

        Snapshots the per-chat states on the GUI thread, then parses every
        stored chat on a worker thread (via :func:`asyncio.to_thread`) and
        applies the result back on the GUI thread. Used by the chat controller's
        debounced streaming refresh so a long stream never blocks on disk I/O.
        """
        states = dict(self._states)

        def _collect() -> tuple[list[dict[str, Any]], list[str]]:
            stored = self.app.chat_store.load_all_chats()
            enriched = [self._enrich_chat(data, states) for data in stored]
            sessions = self.app.chat_store.list_sessions()
            return enriched, sessions

        enriched, sessions = await asyncio.to_thread(_collect)
        self._apply_summaries(enriched, sessions)

    def _collect_summaries(self) -> tuple[list[dict[str, Any]], list[str]]:
        """Read and enrich every chat summary in a single disk pass.

        Parses each chat file once (via ``load_all_chats``) and derives the
        display title and status from that same data. Touches no Qt objects, so it
        is safe to run on a worker thread through ``asyncio.to_thread``.

        Returns:
            ``(enriched, sessions)`` — the enriched summary list and session names.
        """
        states = dict(self._states)
        stored = self.app.chat_store.load_all_chats()
        enriched = [self._enrich_chat(data, states) for data in stored]
        sessions = self.app.chat_store.list_sessions()
        return enriched, sessions

    def _apply_summaries(self, enriched: list[dict[str, Any]], sessions: list[str]) -> None:
        """Apply collected chat summaries to the sidebar model.

        Must run on the GUI thread (updates the ``QAbstractListModel``).

        Args:
            enriched: Enriched chat summary dicts.
            sessions: Session names in display order.
        """
        self.chat_ids = [s["id"] for s in enriched]
        self._enriched = {chat["id"]: chat for chat in enriched}
        for chat in enriched:
            state = self._states.get(chat["id"])
            if state is None:
                state = ChatState(chat["id"])
                self._states[chat["id"]] = state
            if (
                state.true_input_tokens == 0
                and state.true_output_cum == 0
                and chat_manager.get_chat(chat["id"]) is None
            ):
                state.true_input_tokens = int(chat.get("true_input_tokens", 0) or 0)
                state.true_output_cum = int(chat.get("true_output_cum", 0) or 0)
            state.primary_count = chat.get("primary_count", 0)
            state.allow_count = chat.get("allow_count", 0)
            state.ask_count = chat.get("ask_count", 0)
            state.block_count = chat.get("block_count", 0)
            state.model_name = chat.get("model_name") or self.app.config.llm_model_name
        grouped: dict[str, list[str]] = {name: [] for name in sessions}
        for chat in enriched:
            session_name = chat.get("session")
            if session_name in grouped:
                grouped[session_name].append(chat["id"])
        self._chats_by_session = grouped
        self._session_menu_model.set_sessions(sessions, self.active_session_name)
        self.sessions_changed.emit()
        self._sync_panels()

    # ------------------------------------------------------------------
    #  Workspace panels
    # ------------------------------------------------------------------

    def _reconcile_panels(self, name: str) -> None:
        """Rebuild a session's panels from its stored layout and chats.

        Chats in the session but absent from the stored layout are added to the
        first panel; empty panels are dropped (but one is always kept).

        Args:
            name: The session name to reconcile.
        """
        stored = self.app.chat_store.get_layout(name)
        session_chats = self._chats_by_session.get(name, [])
        assigned: set[str] = set()
        panels: list[dict[str, Any]] = []
        for split in (stored.get("splits") or [])[:4]:
            ids = [
                cid
                for cid in split.get("chat_ids", [])
                if cid in session_chats and cid not in assigned
            ]
            assigned.update(ids)
            active = split.get("active_chat_id", "")
            if active not in ids:
                active = ids[0] if ids else ""
            panels.append({"chat_ids": ids, "active_chat_id": active})
        if not panels:
            panels = [{"chat_ids": [], "active_chat_id": ""}]
        leftovers = [cid for cid in session_chats if cid not in assigned]
        if leftovers:
            panels[0]["chat_ids"].extend(leftovers)
            if not panels[0]["active_chat_id"]:
                panels[0]["active_chat_id"] = leftovers[0]
        non_empty = [p for p in panels if p["chat_ids"]]
        self._panels = (non_empty or [{"chat_ids": [], "active_chat_id": ""}])[:4]
        self._save_layout()

    def _sync_panels(self) -> None:
        """Push the layout and per-chat runtime into the panel view models."""
        self._ensure_panel_exists()
        count = len(self._panels)
        while len(self._panel_models) < count:
            self._panel_models.append(ChatPanelModel(len(self._panel_models), self))
        del self._panel_models[count:]
        visible: set[str] = set()
        for index, panel in enumerate(self._panels):
            active = panel["active_chat_id"]
            model = self.chat.model_for(active) if active else None
            tabs = [self._enriched[cid] for cid in panel["chat_ids"] if cid in self._enriched]
            if active:
                visible.add(active)
            panel_model = self._panel_models[index]
            panel_model.set_panel(active, model, tabs, active, self._states)
            panel_model.set_runtime(*self._panel_runtime(active))
        self.chat.set_visible_chats(visible)
        self.panels_changed.emit()
        self.tabs_changed.emit()

    def _panel_runtime(
        self, chat_id: str
    ) -> tuple[bool, bool, str, int, int, bool, int, int, int, int, str]:
        """Return the runtime display tuple for a chat.

        Args:
            chat_id: The chat id.

        Returns:
            ``(busy, approval_visible, approval_text, input_tokens, output_tokens,
            loading, primary_count, allow_count, ask_count, block_count,
            model_name)``.
        """
        if not chat_id:
            return (False, False, "", 0, 0, False, 0, 0, 0, 0, "")
        state = self._states.get(chat_id)
        busy = bool(state and state.is_busy)
        approval_visible = bool(state and state.pending_tool_info)
        approval_text = state.approval_text if state else ""
        loading = bool(state and state.is_loading)
        input_tokens = state.true_input_tokens if state else 0
        output_tokens = state.true_output_cum if state else 0
        primary_count = state.primary_count if state else 0
        allow_count = state.allow_count if state else 0
        ask_count = state.ask_count if state else 0
        block_count = state.block_count if state else 0
        model_name = (
            state.model_name if state and state.model_name else self.app.config.llm_model_name
        )
        return (
            busy,
            approval_visible,
            approval_text,
            input_tokens,
            output_tokens,
            loading,
            primary_count,
            allow_count,
            ask_count,
            block_count,
            model_name,
        )

    def _save_layout(self) -> None:
        """Persist the active session's panel layout to the store."""
        if not self.active_session_name:
            return
        layout = {
            "splits": [
                {"chat_ids": p["chat_ids"], "active_chat_id": p["active_chat_id"]}
                for p in self._panels
            ]
        }
        self.app.chat_store.set_layout(self.active_session_name, layout)

    @Slot(str)
    def refresh_chat_panels(self, chat_id: str) -> None:
        """Refresh a chat's tab status and panel runtime after a state change.

        Pushes the tab dot's status/blink immediately (without waiting for the
        debounced disk refresh) to every panel that owns the chat, and updates
        the runtime values of the panel currently showing it.

        Args:
            chat_id: The chat whose state changed.
        """
        if not chat_id:
            return
        status = self._chat_display_status(chat_id)
        state = self._states.get(chat_id)
        blinking = bool(state and state.is_busy and not state.pending_tool_info)
        for panel_model, panel in zip(self._panel_models, self._panels, strict=False):
            if chat_id in panel["chat_ids"]:
                panel_model.update_tab(chat_id, status, blinking)
            if panel["active_chat_id"] == chat_id:
                panel_model.set_runtime(*self._panel_runtime(chat_id))

    @Slot(str)
    def refresh_chat_tokens(self, chat_id: str) -> None:
        """Push a chat's token counts to the panel currently showing it.

        Called on every ``token_usage`` event so the token bar updates live
        during a turn, without rebuilding the full runtime state.

        Args:
            chat_id: The chat whose token counts changed.
        """
        if not chat_id:
            return
        state = self._states.get(chat_id)
        input_tokens = state.true_input_tokens if state else 0
        output_tokens = state.true_output_cum if state else 0
        for panel_model, panel in zip(self._panel_models, self._panels, strict=False):
            if panel["active_chat_id"] == chat_id:
                panel_model.set_tokens(input_tokens, output_tokens)

    def _open_chat(self, chat_id: str) -> None:
        """Activate and hydrate a chat, then rebuild its display.

        Args:
            chat_id: The chat to open.
        """
        if not chat_id:
            return
        self.active_chat_id = chat_id
        self.chat_switch_started.emit(chat_id)
        self._spawn(self._open_chat_async(chat_id))

    async def _open_chat_async(self, chat_id: str) -> None:
        """Hydrate a chat in the background, then notify activation.

        Args:
            chat_id: The chat to open.
        """
        stored = await asyncio.to_thread(self.app.chat_store.load_chat, chat_id)
        if chat_manager.get_chat(chat_id) is None and stored and stored.get("messages"):
            await self._hydrate_chat(chat_id, stored)
        self.active_chat_changed.emit(chat_id)

    def _open_session_panels(self) -> None:
        """Open the active chat of every panel of the active session."""
        for panel in self._panels:
            chat_id = panel["active_chat_id"]
            if chat_id:
                self._open_chat(chat_id)

    def _enrich_chat(self, stored: dict[str, Any], states: dict[str, ChatState]) -> dict[str, Any]:
        """Attach a derived title and status to a stored chat dict.

        Args:
            stored: A full chat dict from ``ChatStore.load_all_chats``.
            states: Snapshot of the per-chat UI states.

        Returns:
            The summary extended with ``title`` and ``status`` keys.
        """
        chat_id = str(stored.get("id", ""))
        skills = stored.get("skills_config", {}) or {}
        tools = skills.get("tools", {}) or {}
        counts = {
            "primary_count": len(skills.get("primary", []) or []),
            "allow_count": sum(1 for mode in tools.values() if mode == "allow"),
            "ask_count": sum(1 for mode in tools.values() if mode == "ask"),
            "block_count": sum(1 for mode in tools.values() if mode == "block"),
        }
        return {
            "id": chat_id,
            "session": stored.get("session"),
            "skills": stored.get("skills", []),
            "created_at": stored.get("created_at", ""),
            "updated_at": stored.get("updated_at", ""),
            "message_count": stored.get("message_count", 0),
            "model_name": stored.get("model_name") or self.app.config.llm_model_name,
            "title": self._derive_chat_title(stored),
            "status": self._derive_chat_status(chat_id, stored, states),
            "true_input_tokens": int(stored.get("true_input_tokens", 0) or 0),
            "true_output_cum": int(stored.get("true_output_cum", 0) or 0),
            **counts,
        }

    # ------------------------------------------------------------------
    #  Titles and statuses
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_chat_title(sess: dict) -> str:
        """Derive a short display title from the first user message.

        Uses the first user message content (truncated to 30 chars) or falls
        back to the first 15 chars of the chat id.

        Args:
            sess: The stored chat dict.

        Returns:
            A displayable title string.
        """
        for msg in sess.get("messages", []):
            if msg.get("role") == "user" and msg.get("content", "").strip():
                title = msg["content"].strip().replace("\n", " ")
                return title[:30] + ("..." if len(title) > 30 else "")
        return sess.get("id", "")[:15]

    def _derive_chat_status(
        self, cid: str, stored: dict | None, states: dict[str, ChatState]
    ) -> str:
        """Determine a chat's status from its UI state and stored messages.

        Args:
            cid: Chat id.
            stored: The stored chat data dict, or ``None``.
            states: Snapshot of the per-chat UI states.

        Returns:
            One of the :class:`ChatStatus` values.
        """
        has_messages = bool(stored and stored.get("messages"))
        return self._status_from_state(states.get(cid), has_messages)

    def _chat_display_status(self, chat_id: str) -> str:
        """Derive a chat's live display status without a disk read.

        Used by :meth:`refresh_chat_panels` to paint the tab dot the instant a
        chat state changes. Prefers the live agent's messages and falls back to
        the last enriched summary when the chat is not hydrated.

        Args:
            chat_id: The chat id.

        Returns:
            One of the :class:`ChatStatus` values.
        """
        state = self._states.get(chat_id)
        chat = chat_manager.get_chat(chat_id)
        if chat is not None:
            has_messages = bool(chat.messages)
        else:
            enriched = self._enriched.get(chat_id)
            has_messages = bool(enriched and enriched.get("message_count"))
        return self._status_from_state(state, has_messages)

    @staticmethod
    def _status_from_state(state: ChatState | None, has_messages: bool) -> str:
        """Map a chat's UI state and message presence to a display status.

        Args:
            state: The chat's UI state, or ``None``.
            has_messages: Whether the chat has any messages.

        Returns:
            One of the :class:`ChatStatus` values.
        """
        if state and state.is_busy:
            return ChatStatus.WAITING if state.pending_tool_info else ChatStatus.RUNNING
        if state and state.has_error:
            return ChatStatus.ERROR
        return ChatStatus.FINISHED if has_messages else ChatStatus.EMPTY

    # ------------------------------------------------------------------
    #  Context snapshot
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context_snapshot(session: Any) -> dict[str, Any]:
        """Build a context snapshot dict from a live chat object.

        Args:
            session: The live chat object from ``chat_manager``.

        Returns:
            A dict with system_prompt, pending_additions, primary_skills,
            secondary_skills, tools, and tool_config.
        """
        return {
            "system_prompt": session.sys_prompt,
            "pending_additions": session._pending_sys_message,
            "primary_skills": session.primary_skills,
            "secondary_skills": session.secondary_skills,
            "tools": session._tools,
            "tool_config": session._tool_config,
        }

    # ------------------------------------------------------------------
    #  Persistence
    # ------------------------------------------------------------------

    def _create_stored_chat(self, chat_id: str, source_chat_id: str = "") -> None:
        """Write a new empty chat record to the store.

        When ``source_chat_id`` refers to an existing chat, its skill/tool config
        and model are carried over so the new chat starts from the last working
        setup. Otherwise the config is empty and the model is the config default.

        Args:
            chat_id: The chat id to create.
            source_chat_id: Optional chat whose config/model to inherit.
        """
        source = self.app.chat_store.load_chat(source_chat_id) if source_chat_id else None
        skills_config = (source or {}).get("skills_config") or {
            "primary": [],
            "secondary": [],
            "tools": {},
        }
        model_name = (source or {}).get("model_name") or self.app.config.llm_model_name
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.app.chat_store.save_chat(
            chat_id,
            {
                "id": chat_id,
                "skills_config": skills_config,
                "messages": [],
                "session": self.active_session_name or DEFAULT_SESSION_NAME,
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
                "model_name": model_name,
                "true_input_tokens": 0,
                "true_output_cum": 0,
            },
        )

    def _chat_save_snapshot(
        self, chat_id: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        """Capture a live chat's messages and context on the GUI thread.

        Args:
            chat_id: The chat id to snapshot.

        Returns:
            ``(messages, context_snapshot)``, or ``None`` when no live chat
            exists for the id.
        """
        chat = chat_manager.get_chat(chat_id)
        if chat is None:
            return None
        return list(chat.messages), self._build_context_snapshot(chat)

    def _save_current_chat_for(
        self,
        chat_id: str,
        snapshot: tuple[list[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        """Persist live in-memory messages and context for a chat.

        Args:
            chat_id: The chat id to persist.
            snapshot: Optional ``(messages, context_snapshot)`` captured on the
                GUI thread. Passed when this runs on a worker thread so a message
                list being appended to concurrently is not serialized mid-mutation.
        """
        if not chat_id:
            return
        if snapshot is None:
            snapshot = self._chat_save_snapshot(chat_id)
            if snapshot is None:
                return
        messages, context_snapshot = snapshot
        stored = self.app.chat_store.load_chat(chat_id)
        if stored:
            stored["messages"] = messages
            stored["message_count"] = len(messages)
            stored["context_snapshot"] = context_snapshot
            state = self._states.get(chat_id)
            if state is not None:
                stored["true_input_tokens"] = state.true_input_tokens
                stored["true_output_cum"] = state.true_output_cum
            self.app.chat_store.save_chat(chat_id, stored)

    def _generate_unique_chat_id(self) -> str:
        """Return a timestamp-based chat id that is not already in use.

        Returns:
            A unique chat id string.
        """
        base = time.strftime("%Y%m%d_%H%M%S")
        candidate = base
        suffix = 1
        existing = set(self.app.chat_store.list_chat_ids())
        existing.update(self.chat_ids)
        while candidate in existing:
            suffix += 1
            candidate = f"{base}_{suffix}"
        return candidate

    # ------------------------------------------------------------------
    #  Hydration
    # ------------------------------------------------------------------

    async def _hydrate_chat(self, chat_id: str, stored: dict | None = None) -> Any:
        """Restore a chat from persistent storage into the chat manager.

        Args:
            chat_id: The chat id to hydrate.
            stored: Optional pre-loaded stored chat data. Loaded from the
                store when ``None``.

        Returns:
            The hydrated chat object, or ``None`` on failure.
        """
        existing = chat_manager.get_chat(chat_id)
        if existing is not None:
            return existing
        if stored is None:
            stored = await asyncio.to_thread(self.app.chat_store.load_chat, chat_id)
        if not stored:
            self.toast_requested.emit(f"Chat '{chat_id}' not found.", TOAST_ERROR)
            return None

        skills_cfg = stored.get("skills_config", {})
        primary = skills_cfg.get("primary", [])
        secondary = skills_cfg.get("secondary", [])
        try:
            session = await asyncio.to_thread(
                self._create_manager_chat, chat_id, stored, primary, secondary
            )
        except Exception as error:
            chat_error = ChatError(
                brief=f"Failed to create chat '{chat_id}'",
                detail=str(error),
            )
            logger.error("%s", chat_error.detail)
            self.toast_requested.emit(chat_error.brief, TOAST_ERROR)
            return None

        await session.refresh_estimated()
        state = self._states.get(chat_id)
        if state is not None and state.true_input_tokens == 0 and state.true_output_cum == 0:
            state.true_input_tokens = int(stored.get("true_input_tokens", 0) or 0)
            state.true_output_cum = int(stored.get("true_output_cum", 0) or 0)
        if not stored.get("context_snapshot"):
            stored["context_snapshot"] = self._build_context_snapshot(session)
            await asyncio.to_thread(self.app.chat_store.save_chat, chat_id, stored)
        return session

    def _create_manager_chat(
        self,
        chat_id: str,
        stored: dict,
        primary: list[str],
        secondary: list[str],
    ) -> Any:
        """Create the live manager chat from stored skill/tool config.

        Args:
            chat_id: The chat id.
            stored: The stored chat data dict.
            primary: Selected primary skill paths.
            secondary: Selected secondary skill paths.

        Returns:
            The newly created chat from ``chat_manager``.
        """
        tools_cfg = stored.get("skills_config", {}).get("tools", {})
        model_name = stored.get("model_name") or self.app.config.llm_model_name
        if model_name not in self.app.config.llm_models:
            model_name = self.app.config.llm_model_name
        return chat_manager.create_chat(
            chat_id=chat_id,
            model=self.app.config.llm_config(model_name),
            primary_skill_contents=self.app.skill_manager.load_skill_contents(primary),
            secondary_skill_contents=self.app.skill_manager.load_skill_contents(secondary),
            tool_functions=self.app.skill_manager.load_tool_functions(primary),
            tool_config=self.app.skill_manager.build_tool_config(tools_cfg, primary),
            skills_dir=self.app.config.skills_dir,
            system_message=self.app.config.agent_system_prompt,
            initial_messages=stored.get("messages", []),
            summary_prompt=self.app.config.agent_summary_prompt,
            chat_limits={
                "max_bytes": self.app.config.chat_max_bytes,
                "max_tokens": self.app.config.chat_max_tokens,
            },
        )

    # ------------------------------------------------------------------
    #  Switching
    # ------------------------------------------------------------------

    def open_chat_after(self, source_chat_id: str, new_chat_id: str) -> None:
        """Add a new chat as a tab after its source chat and open it.

        Used by chat compaction. The new chat joins the panel holding the source
        chat (or the first panel when the source is not found).

        Args:
            source_chat_id: The chat the new one was derived from.
            new_chat_id: The id of the chat to add and activate.
        """
        target = None
        for panel in self._panels:
            if source_chat_id in panel["chat_ids"]:
                target = panel
                break
        if target is None:
            target = self._panels[0]
        target["chat_ids"].append(new_chat_id)
        target["active_chat_id"] = new_chat_id
        self._refresh_model()
        self._save_layout()
        self._open_chat(new_chat_id)

    # ------------------------------------------------------------------
    #  Deletion
    # ------------------------------------------------------------------

    def _delete_chat_by_id(self, chat_id: str) -> None:
        """Delete a chat, removing it from its panel.

        Args:
            chat_id: The chat id to delete.
        """
        logger.info("Deleted chat '%s'", chat_id)
        was_active = self.active_chat_id == chat_id
        self._forget_chat(chat_id)
        self.app.chat_store.delete_chat(chat_id)
        self._remove_chat_from_panels(chat_id)
        self._ensure_panel_exists()
        self._refresh_model()
        if was_active:
            for panel in self._panels:
                if panel["active_chat_id"]:
                    self._open_chat(panel["active_chat_id"])
                    return
            self.active_chat_id = None
            self.active_chat_changed.emit("")

    def _forget_chat(self, chat_id: str) -> None:
        """Drop in-memory state for a chat without touching the store.

        Args:
            chat_id: The chat id to forget.
        """
        state = self._states.pop(chat_id, None)
        if state:
            self._cancel_pending_operations(state, chat_id)
        chat_manager.remove_chat(chat_id)

    # ------------------------------------------------------------------
    #  Pending operations
    # ------------------------------------------------------------------

    def _cancel_pending_operations(self, state: ChatState, chat_id: str) -> None:
        """Cancel pending approvals and the active generation task.

        Args:
            state: The chat's UI state.
            chat_id: The chat id.
        """
        pending_info = state.pending_tool_info
        if pending_info:
            chat = chat_manager.get_chat(chat_id)
            if chat:
                self._spawn(chat.deny_tool(pending_info.get("id", "")))
        if state.approval_event and not state.approval_event.is_set():
            state.approval_event.set()
        if state.active_task and not state.active_task.done():
            state.active_task.cancel()

    # ------------------------------------------------------------------
    #  Tasks
    # ------------------------------------------------------------------

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Schedule a coroutine and keep a reference until it completes.

        Args:
            coro: The coroutine to schedule on the running event loop.
        """
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # ------------------------------------------------------------------
    #  Validation
    # ------------------------------------------------------------------

    def _emit_validation_issues(self) -> None:
        """Emit toasts for skill validation errors and warnings."""
        from ..skill.models import ValidationLevel

        issues = self.app.skill_manager.get_validation_issues()
        if not issues:
            return
        warnings = [
            f"{i.source}: {i.message}" for i in issues if i.level == ValidationLevel.WARNING
        ]
        errors = [f"{i.source}: {i.message}" for i in issues if i.level == ValidationLevel.ERROR]
        if warnings:
            self.toast_requested.emit("\n".join(warnings), TOAST_WARNING)
        if errors:
            self.toast_requested.emit("\n".join(errors), TOAST_ERROR)
