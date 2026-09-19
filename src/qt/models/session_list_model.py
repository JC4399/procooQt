"""``SessionListModel`` — session and folder rows rendered by ``SessionPanel.qml``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.base import Item, ListModel
from ..qt_roles import SessionRole, role_names

if TYPE_CHECKING:
    from ..session_state import SessionState


class SessionListModel(ListModel):
    """List model of folder headers and session tiles.

    Rows are flattened from stored session summaries and folder names. A folder
    header row is always emitted; its session rows follow only while the folder
    is expanded (see :meth:`set_folder_expansion`). Unfiled sessions are
    rendered directly after the folders with no synthetic header, matching the
    Flet edition's unfiled drop zone. Session summaries must be pre-enriched by
    the controller with ``title`` and ``status`` keys.

    Attributes:
        roles: Session role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the session list model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(SessionRole), parent)
        self._expanded: dict[str, bool] = {}

    # ------------------------------------------------------------------
    #  Public: folder expansion
    # ------------------------------------------------------------------

    def set_folder_expansion(self, name: str, expanded: bool) -> None:
        """Record a folder's expansion state used by :meth:`set_sessions`.

        Args:
            name: The folder name.
            expanded: Whether the folder's session rows should be shown.
        """
        self._expanded[name] = expanded

    def is_expanded(self, name: str) -> bool:
        """Return whether a folder's session rows are currently shown.

        Args:
            name: The folder name.

        Returns:
            ``True`` if the folder is expanded.
        """
        return self._expanded.get(name, False)

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def set_sessions(
        self,
        sessions: list[dict[str, Any]],
        folders: list[str],
        active_id: str | None,
        states: dict[str, SessionState],
    ) -> None:
        """Flatten folder headers and session tiles into model rows.

        Args:
            sessions: Session summary dicts, enriched by the controller with
                ``title`` and ``status`` keys.
            folders: Folder names in display order.
            active_id: The currently active session id, or ``None``.
            states: Per-session states used to derive the blink flag.
        """
        rows: list[Item] = []
        keys: list[str] = []
        for folder in folders:
            folder_sessions = [s for s in sessions if s.get("folder") == folder]
            self._append_folder(rows, keys, folder, len(folder_sessions))
            if self.is_expanded(folder):
                for session in folder_sessions:
                    self._append_session(rows, keys, session, active_id, states)
        for session in sessions:
            if not session.get("folder"):
                self._append_session(rows, keys, session, active_id, states)
        self.set_items(rows, keys)

    # ------------------------------------------------------------------
    #  Private: row builders
    # ------------------------------------------------------------------

    def _append_folder(
        self,
        rows: list[Item],
        keys: list[str],
        folder: str,
        session_count: int,
    ) -> None:
        """Append a folder header row.

        ``MESSAGE_COUNT`` carries the folder's session count for headers.

        Args:
            rows: Row accumulator.
            keys: Key accumulator.
            folder: The folder name.
            session_count: Number of sessions filed in the folder.
        """
        rows.append(
            {
                int(SessionRole.SESSION_ID): "",
                int(SessionRole.TITLE): folder,
                int(SessionRole.STATUS): "",
                int(SessionRole.FOLDER): folder,
                int(SessionRole.IS_FOLDER): True,
                int(SessionRole.IS_ACTIVE): False,
                int(SessionRole.IS_BLINKING): False,
                int(SessionRole.MESSAGE_COUNT): session_count,
            }
        )
        keys.append(f"folder:{folder}")

    def _append_session(
        self,
        rows: list[Item],
        keys: list[str],
        session: dict[str, Any],
        active_id: str | None,
        states: dict[str, SessionState],
    ) -> None:
        """Append a session tile row.

        Args:
            rows: Row accumulator.
            keys: Key accumulator.
            session: Enriched session summary dict.
            active_id: The active session id, or ``None``.
            states: Per-session states used to derive the blink flag.
        """
        session_id = str(session.get("id", ""))
        state = states.get(session_id)
        blinking = bool(state and state.is_busy and not state.pending_tool_info)
        rows.append(
            {
                int(SessionRole.SESSION_ID): session_id,
                int(SessionRole.TITLE): session.get("title", session_id[:15]),
                int(SessionRole.STATUS): session.get("status", ""),
                int(SessionRole.FOLDER): session.get("folder") or "",
                int(SessionRole.IS_FOLDER): False,
                int(SessionRole.IS_ACTIVE): session_id == active_id,
                int(SessionRole.IS_BLINKING): blinking,
                int(SessionRole.MESSAGE_COUNT): session.get("message_count", 0),
            }
        )
        keys.append(f"session:{session_id}")
