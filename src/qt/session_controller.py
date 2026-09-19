"""``SessionController`` — session sidebar, lifecycle, and persistence.

Owns the session list model and the per-session :class:`SessionState` registry.
Behavior ports from ``src/flet/session_panel.py`` and ``src/flet/session_lifecycle.py``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..session.manager import session_manager
from ..util.error.types import SessionError
from .error_handler import TOAST_ERROR, TOAST_WARNING
from .models.session_list_model import SessionListModel
from .session_state import SessionState
from .theme import (
    COLOR_SESSION_EMPTY,
    COLOR_SESSION_ERROR,
    COLOR_SESSION_FINISHED,
    COLOR_SESSION_RUNNING,
    COLOR_SESSION_WAITING,
)

if TYPE_CHECKING:
    from ..app import ProcooApp

logger = logging.getLogger("procoo_qt")


class SessionStatus:
    """String constants for session display statuses."""

    EMPTY = "empty"
    RUNNING = "running"
    WAITING = "waiting"
    FINISHED = "finished"
    ERROR = "error"


_STATUS_COLORS: dict[str, str] = {
    SessionStatus.EMPTY: COLOR_SESSION_EMPTY,
    SessionStatus.FINISHED: COLOR_SESSION_FINISHED,
    SessionStatus.WAITING: COLOR_SESSION_WAITING,
    SessionStatus.RUNNING: COLOR_SESSION_RUNNING,
    SessionStatus.ERROR: COLOR_SESSION_ERROR,
}


class SessionController(QObject):
    """Session list, creation/switching/deletion, and persistence controller."""

    sessions_changed = Signal()
    active_session_changed = Signal(str)
    toast_requested = Signal(str, str)
    new_folder_requested = Signal()

    if TYPE_CHECKING:
        app: ProcooApp
        _session_model: SessionListModel
        _states: dict[str, SessionState]
        _tasks: set[asyncio.Task[Any]]
        active_session_id: str | None
        session_ids: list[str]

        def _get_or_create_state(self, session_id: str) -> SessionState: ...
        def _save_current_session_for(self, session_id: str) -> None: ...

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the session controller.

        Args:
            app: The top-level application holding backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the session model and per-session state registry."""
        self._session_model = SessionListModel(self)
        self._states = {}
        self._tasks = set()
        self.active_session_id = None
        self.session_ids = [s["id"] for s in self.app.session_store.list_sessions()]
        self._refresh_model()

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=sessions_changed)
    def session_model(self) -> SessionListModel:
        """Return the flattened session/folder list model.

        Returns:
            The model exposed to QML as ``session.session_model``.
        """
        return self._session_model

    # ------------------------------------------------------------------
    #  State
    # ------------------------------------------------------------------

    def state(self, session_id: str) -> SessionState:
        """Return the state for a session, creating it on demand.

        Args:
            session_id: The session id.

        Returns:
            The session's UI state.
        """
        if session_id not in self._states:
            self._states[session_id] = SessionState(session_id)
        return self._states[session_id]

    def _get_or_create_state(self, session_id: str) -> SessionState:
        """Return the state for a session, creating it on demand.

        Args:
            session_id: The session id.

        Returns:
            The session's UI state.
        """
        return self.state(session_id)

    # ------------------------------------------------------------------
    #  Slot: Start
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Emit startup validation issues and auto-select a session."""
        self._emit_validation_issues()
        self._auto_select_session()

    # ------------------------------------------------------------------
    #  Slot: New session
    # ------------------------------------------------------------------

    @Slot()
    def _handle_new_session(self) -> None:
        """Create a new session with default config and switch to it.

        Skill/tool sidebar selections are wired in P6; until then a new
        session starts from an empty primary/secondary/tool config.
        """
        session_id = self._generate_unique_session_id()
        self._create_stored_session(session_id)
        self.session_ids = [session_id, *self.session_ids]
        self._spawn(self._switch_to_session(session_id))

    # ------------------------------------------------------------------
    #  Slot: Session click
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_session_click(self, session_id: str) -> None:
        """Switch to the clicked session.

        Args:
            session_id: The session id to switch to.
        """
        if not session_id:
            return
        self._spawn(self._switch_to_session(session_id))

    # ------------------------------------------------------------------
    #  Slot: Delete session
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_delete_session(self, session_id: str) -> None:
        """Delete a session and select a replacement if it was active.

        Args:
            session_id: The session id to delete.
        """
        if not session_id:
            return
        self._delete_session_by_id(session_id)

    # ------------------------------------------------------------------
    #  Slot: New folder
    # ------------------------------------------------------------------

    @Slot()
    def _handle_new_folder(self) -> None:
        """Request that QML open the new-folder dialog."""
        self.new_folder_requested.emit()

    # ------------------------------------------------------------------
    #  Slot: Create folder
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_create_folder(self, name: str) -> None:
        """Create a folder and refresh the sidebar.

        Args:
            name: The folder name entered in the dialog.
        """
        cleaned = (name or "").strip()
        if not cleaned:
            self.toast_requested.emit("Please enter a folder name.", TOAST_ERROR)
            return
        try:
            self.app.session_store.create_folder(cleaned)
        except ValueError as error:
            self.toast_requested.emit(str(error), TOAST_ERROR)
            return
        self._session_model.set_folder_expansion(cleaned, True)
        self._refresh_model()

    # ------------------------------------------------------------------
    #  Slot: Delete folder
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_delete_folder(self, name: str) -> None:
        """Delete a folder, unlinking its sessions.

        Args:
            name: The folder name to delete.
        """
        if not name:
            return
        try:
            self.app.session_store.delete_folder(name)
        except ValueError as error:
            self.toast_requested.emit(str(error), TOAST_ERROR)
            return
        self._refresh_model()

    # ------------------------------------------------------------------
    #  Slot: Drop on folder
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _handle_drop_on_folder(self, session_id: str, folder: str) -> None:
        """Move a dragged session into a folder, or unfiled when empty.

        Mirrors the Flet edition's ``_on_drop_on_folder``: the target folder is
        ``None`` for the unfiled drop zone. A missing session surfaces as a toast.

        Args:
            session_id: The dragged session id.
            folder: Target folder name, or an empty string for the unfiled zone.
        """
        if not session_id:
            return
        try:
            self.app.session_store.set_session_folder(session_id, folder or None)
        except ValueError as error:
            self.toast_requested.emit(str(error), TOAST_ERROR)
            return
        self._refresh_model()

    # ------------------------------------------------------------------
    #  Slot: Folder expansion
    # ------------------------------------------------------------------

    @Slot(str, bool)
    def _handle_folder_expansion(self, name: str, expanded: bool) -> None:
        """Toggle a folder's expansion and refresh the sidebar rows.

        Args:
            name: The folder name.
            expanded: Whether the folder should be expanded.
        """
        if not name:
            return
        self._session_model.set_folder_expansion(name, expanded)
        self._refresh_model()

    @Slot(str, result=bool)
    def is_folder_expanded(self, name: str) -> bool:
        """Return whether a folder's session rows are shown.

        Args:
            name: The folder name.

        Returns:
            ``True`` if the folder is expanded.
        """
        return self._session_model.is_expanded(name)

    # ------------------------------------------------------------------
    #  Slot: Status color
    # ------------------------------------------------------------------

    @Slot(str, result=str)
    def statusColor(self, status: str) -> str:  # noqa: N802
        """Return the theme color for a session status.

        Args:
            status: One of the :class:`SessionStatus` strings.

        Returns:
            A hex color string suitable for a QML dot.
        """
        return _STATUS_COLORS.get(status, COLOR_SESSION_EMPTY)

    # ------------------------------------------------------------------
    #  Session model
    # ------------------------------------------------------------------

    def _refresh_model(self) -> None:
        """Reload session summaries and folders into the list model."""
        summaries = self.app.session_store.list_sessions()
        self.session_ids = [s["id"] for s in summaries]
        enriched = [self._enrich_session(summary) for summary in summaries]
        folders = self.app.session_store.list_folders()
        self._session_model.set_sessions(enriched, folders, self.active_session_id, self._states)
        self.sessions_changed.emit()

    def _enrich_session(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Attach a derived title and status to a session summary.

        Args:
            summary: A summary dict from ``SessionStore.list_sessions``.

        Returns:
            The summary extended with ``title`` and ``status`` keys.
        """
        session_id = summary["id"]
        stored = self.app.session_store.load_session(session_id)
        return {
            **summary,
            "title": self._derive_session_title(stored or {"id": session_id}),
            "status": self._derive_session_status(session_id, stored),
        }

    # ------------------------------------------------------------------
    #  Titles and statuses
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_session_title(sess: dict) -> str:
        """Derive a short display title from the first user message.

        Uses the first user message content (truncated to 30 chars) or falls
        back to the first 15 chars of the session id.

        Args:
            sess: The stored session dict.

        Returns:
            A displayable title string.
        """
        for msg in sess.get("messages", []):
            if msg.get("role") == "user" and msg.get("content", "").strip():
                title = msg["content"].strip().replace("\n", " ")
                return title[:30] + ("..." if len(title) > 30 else "")
        return sess.get("id", "")[:15]

    def _derive_session_status(self, sid: str, stored: dict | None) -> str:
        """Determine a session's status from its UI state and stored messages.

        Args:
            sid: Session id.
            stored: The stored session data dict, or ``None``.

        Returns:
            One of the :class:`SessionStatus` values.
        """
        state = self._states.get(sid)
        if state and state.is_busy:
            return SessionStatus.WAITING if state.pending_tool_info else SessionStatus.RUNNING
        if not stored:
            return SessionStatus.EMPTY
        if not stored.get("messages"):
            return SessionStatus.EMPTY
        return SessionStatus.FINISHED

    # ------------------------------------------------------------------
    #  Context snapshot
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context_snapshot(session: Any) -> dict[str, Any]:
        """Build a context snapshot dict from a live session object.

        Args:
            session: The live session object from ``session_manager``.

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

    def _create_stored_session(self, session_id: str) -> None:
        """Write a new empty session record to the store.

        Args:
            session_id: The session id to create.
        """
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.app.session_store.save_session(
            session_id,
            {
                "id": session_id,
                "skills_config": {"primary": [], "secondary": [], "tools": {}},
                "messages": [],
                "folder": None,
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
            },
        )

    def _save_current_session_for(self, session_id: str) -> None:
        """Persist live in-memory messages and context for a session.

        Args:
            session_id: The session id to persist.
        """
        if not session_id:
            return
        session = session_manager.get_session(session_id)
        if not session:
            return
        stored = self.app.session_store.load_session(session_id)
        if stored:
            stored["messages"] = session.messages
            stored["message_count"] = len(session.messages)
            stored["context_snapshot"] = self._build_context_snapshot(session)
            self.app.session_store.save_session(session_id, stored)

    def _generate_unique_session_id(self) -> str:
        """Return a timestamp-based session id that is not already in use.

        Returns:
            A unique session id string.
        """
        base = time.strftime("%Y%m%d_%H%M%S")
        candidate = base
        suffix = 1
        existing = {s["id"] for s in self.app.session_store.list_sessions()}
        existing.update(self.session_ids)
        while candidate in existing:
            suffix += 1
            candidate = f"{base}_{suffix}"
        return candidate

    # ------------------------------------------------------------------
    #  Hydration
    # ------------------------------------------------------------------

    async def _hydrate_session(self, session_id: str, stored: dict | None = None) -> Any:
        """Restore a session from persistent storage into the session manager.

        Args:
            session_id: The session id to hydrate.
            stored: Optional pre-loaded stored session data. Loaded from the
                store when ``None``.

        Returns:
            The hydrated session object, or ``None`` on failure.
        """
        existing = session_manager.get_session(session_id)
        if existing is not None:
            return existing
        if stored is None:
            stored = self.app.session_store.load_session(session_id)
        if not stored:
            self.toast_requested.emit(f"Session '{session_id}' not found.", TOAST_ERROR)
            return None

        skills_cfg = stored.get("skills_config", {})
        primary = skills_cfg.get("primary", [])
        secondary = skills_cfg.get("secondary", [])
        try:
            session = await self._create_manager_session(session_id, stored, primary, secondary)
        except Exception as error:
            session_error = SessionError(
                brief=f"Failed to create session '{session_id}'",
                detail=str(error),
            )
            logger.error("%s", session_error.detail)
            self.toast_requested.emit(session_error.brief, TOAST_ERROR)
            return None

        await session.refresh_estimated()
        if not stored.get("context_snapshot"):
            stored["context_snapshot"] = self._build_context_snapshot(session)
            self.app.session_store.save_session(session_id, stored)
        return session

    async def _create_manager_session(
        self,
        session_id: str,
        stored: dict,
        primary: list[str],
        secondary: list[str],
    ) -> Any:
        """Create the live manager session from stored skill/tool config.

        Args:
            session_id: The session id.
            stored: The stored session data dict.
            primary: Selected primary skill paths.
            secondary: Selected secondary skill paths.

        Returns:
            The newly created session from ``session_manager``.
        """
        tools_cfg = stored.get("skills_config", {}).get("tools", {})
        return await session_manager.create_session(
            session_id=session_id,
            model={
                "model_name": self.app.config.llm_model_name,
                "api_key": self.app.config.llm_api_key,
                "api_base": self.app.config.llm_api_base,
            },
            primary_skill_contents=self.app.skill_manager.load_skill_contents(primary),
            secondary_skill_contents=self.app.skill_manager.load_skill_contents(secondary),
            tool_functions=self.app.skill_manager.load_tool_functions(primary),
            tool_config=self.app.skill_manager.build_tool_config(tools_cfg, primary),
            skills_dir=self.app.config.skills_dir,
            system_message=self.app.config.agent_system_prompt,
            initial_messages=stored.get("messages", []),
            summary_prompt=self.app.config.agent_summary_prompt,
            session_limits={
                "max_bytes": self.app.config.session_max_bytes,
                "max_tokens": self.app.config.session_max_tokens,
            },
        )

    # ------------------------------------------------------------------
    #  Switching
    # ------------------------------------------------------------------

    async def _switch_to_session(self, session_id: str) -> None:
        """Save the previous session, then activate and hydrate the target.

        Args:
            session_id: The session id to switch to.
        """
        old_sid = self.active_session_id
        if old_sid and old_sid != session_id:
            self._save_current_session_for(old_sid)
        self.active_session_id = session_id
        self._get_or_create_state(session_id)
        self._refresh_model()
        self.active_session_changed.emit(session_id)
        stored = self.app.session_store.load_session(session_id)
        if session_manager.get_session(session_id) is None and stored and stored.get("messages"):
            await self._hydrate_session(session_id, stored)

    # ------------------------------------------------------------------
    #  Auto-select
    # ------------------------------------------------------------------

    def _auto_select_session(self) -> None:
        """Select the latest session on startup, creating one if none exist."""
        if self.session_ids:
            latest_id = self.session_ids[0]
            logger.info("Auto-selecting session '%s' on startup", latest_id)
            self._spawn(self._switch_to_session(latest_id))
            return
        session_id = time.strftime("%Y%m%d_%H%M%S")
        self._create_stored_session(session_id)
        logger.info("Created new session '%s' on startup", session_id)
        self.session_ids = [session_id, *self.session_ids]
        self.active_session_id = session_id
        self._get_or_create_state(session_id)
        self._refresh_model()
        self.active_session_changed.emit(session_id)

    # ------------------------------------------------------------------
    #  Deletion
    # ------------------------------------------------------------------

    def _delete_session_by_id(self, session_id: str) -> None:
        """Delete a session, cancelling tasks and selecting a replacement.

        Args:
            session_id: The session id to delete.
        """
        logger.info("Deleted session '%s'", session_id)
        state = self._states.pop(session_id, None)
        if state:
            self._cancel_pending_operations(state, session_id)
        session_manager.remove_session(session_id)
        self.app.session_store.delete_session(session_id)

        was_active = self.active_session_id == session_id
        self.session_ids = [s for s in self.session_ids if s != session_id]
        if was_active:
            self.active_session_id = self.session_ids[0] if self.session_ids else None
        self._refresh_model()
        if not was_active:
            return
        if self.active_session_id:
            self._spawn(self._switch_to_session(self.active_session_id))
        else:
            self.active_session_changed.emit("")

    # ------------------------------------------------------------------
    #  Pending operations
    # ------------------------------------------------------------------

    def _cancel_pending_operations(self, state: SessionState, session_id: str) -> None:
        """Cancel pending approvals and the active generation task.

        Args:
            state: The session's UI state.
            session_id: The session id.
        """
        pending_info = state.pending_tool_info
        if pending_info:
            session = session_manager.get_session(session_id)
            if session:
                self._spawn(session.deny_tool(pending_info.get("id", "")))
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
