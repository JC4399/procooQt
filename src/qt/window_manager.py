"""``WindowManager`` — opens, focuses, and closes per-session chat windows.

Every Procoo window is a full app window bound to one **session**. The primary
window (``Main.qml``) is registered by :mod:`src.app`; secondary windows are
created on demand from the control server or the title bar. Each window owns a
private :class:`SessionController` / :class:`ChatController` /
:class:`SkillController` triple built by :class:`~src.qt.ui.ProcooQtUI`, so its
panels, tabs, and skill dock are independent of other windows.

The manager also owns the shared editor and notification-history windows: it
lazily instantiates each from its own QML file on the engine root context and
caches the singleton instance. Because they are created standalone (never
declared inside ``Main.qml``), they carry no implicit transient parent and
behave as independent top-level windows.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtQml import QQmlComponent, QQmlContext

from . import native_frame

if TYPE_CHECKING:
    from PySide6.QtGui import QWindow
    from PySide6.QtQuick import QQuickWindow

    from ..app import ProcooApp
    from .chat_controller import ChatController
    from .session_bus import SessionBus
    from .session_controller import SessionController
    from .skill_controller import SkillController

logger = logging.getLogger("procoo_qt")

_WINDOW_QML = Path(__file__).resolve().parent.parent / "qml" / "windows" / "ChatWindow.qml"
_EDITOR_WINDOW_QML = (
    Path(__file__).resolve().parent.parent / "qml" / "windows" / "EditorWindow.qml"
)
_HISTORY_WINDOW_QML = (
    Path(__file__).resolve().parent.parent / "qml" / "windows" / "NotificationHistoryWindow.qml"
)


@dataclass
class WindowRecord:
    """One open chat window and the controllers bound to its session.

    Attributes:
        session_name: The session the window currently shows.
        session: The window's session/layout controller.
        chat: The window's chat rendering controller.
        skill: The window's skill-dock controller.
        window: The top-level QML window.
        context: The private QML context holding the window's controllers.
        component: The component the window was instantiated from.
        frame_filter: The native-frame event filter to keep referenced.
        is_primary: Whether this is the primary (``Main.qml``) window.
    """

    session_name: str
    session: SessionController
    chat: ChatController
    skill: SkillController
    window: QWindow
    context: QQmlContext | None = None
    component: QQmlComponent | None = None
    frame_filter: Any = None
    is_primary: bool = False


@dataclass
class ToolWindowRecord:
    """One cached singleton tool window (editor or notification history).

    Attributes:
        window: The top-level QML window.
        component: The component the window was instantiated from.
    """

    window: QWindow
    component: QQmlComponent


class WindowManager(QObject):
    """Registry and factory for per-session chat windows and shared tool windows.

    Attributes:
        windows_changed: Emitted whenever the set of open windows changes.
    """

    windows_changed = Signal()

    if TYPE_CHECKING:
        app: ProcooApp
        _primary: WindowRecord | None
        _windows: dict[str, WindowRecord]
        _bus: SessionBus
        _editor_window: ToolWindowRecord | None
        _history_window: ToolWindowRecord | None
        _factory: Callable[
            [], tuple[QQmlContext, SessionController, ChatController, SkillController]
        ]

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(
        self,
        app: ProcooApp,
        engine: Any,
        factory: Callable[
            [], tuple[QQmlContext, SessionController, ChatController, SkillController]
        ],
        bus: SessionBus,
        qt_app: Any = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialise the window manager.

        Args:
            app: The top-level application holding backend subsystems.
            engine: The QML engine used to instantiate window components.
            factory: Builds a fresh ``(context, session, chat, skill)`` bundle for
                a new window, wiring cross-controller signals as needed.
            bus: The shared session-change broadcast hub.
            qt_app: The running ``QApplication`` (for native-frame installation).
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._engine = engine
        self._qt_app = qt_app
        self._factory = factory
        self._bus = bus
        self._primary = None
        self._windows = {}
        self._editor_window = None
        self._history_window = None

    # ------------------------------------------------------------------
    #  Public: Primary window
    # ------------------------------------------------------------------

    def register_primary(
        self,
        session: SessionController,
        chat: ChatController,
        skill: SkillController,
        window: QWindow,
        frame_filter: Any = None,
    ) -> None:
        """Register the primary (``Main.qml``) window.

        Args:
            session: The primary window's session controller.
            chat: The primary window's chat controller.
            skill: The primary window's skill controller.
            window: The primary top-level window.
            frame_filter: The native-frame event filter to keep referenced.
        """
        self._primary = WindowRecord(
            session_name=session.active_session_name or "",
            session=session,
            chat=chat,
            skill=skill,
            window=window,
            frame_filter=frame_filter,
            is_primary=True,
        )
        self.windows_changed.emit()

    # ------------------------------------------------------------------
    #  Slot: Open / create / close
    # ------------------------------------------------------------------

    @Slot(str, result=bool)
    def open_session(self, name: str) -> bool:
        """Focus an existing window for a session, or open a new one.

        Args:
            name: The session name to show.

        Returns:
            ``True`` when the session exists and a window is showing it.
        """
        if not name or self.app.chat_store.get_session(name) is None:
            return False
        record = self._find_window(name)
        if record is not None:
            self._focus(record)
            return True
        return self._spawn_window(name) is not None

    @Slot(str, str, result=str)
    def create_session(self, name: str, session_id: str = "") -> str:
        """Create a session (if needed) and open it in a window.

        Args:
            name: The session name.
            session_id: Optional stable UUID supplied by the caller.

        Returns:
            The session's stable id, or an empty string when the name is invalid.
        """
        cleaned = (name or "").strip()
        if not cleaned:
            return ""
        existing = self.app.chat_store.get_session(cleaned)
        if existing is not None:
            self.open_session(cleaned)
            return str(existing.get("id", ""))
        try:
            stable_id = self.app.chat_store.create_session(cleaned, session_id=session_id or None)
        except ValueError as error:
            logger.warning("Session create failed: %s", error)
            return ""
        self._bus.sessions_changed.emit()
        if not self.open_session(cleaned):
            return ""
        record = self._windows.get(cleaned)
        if record is not None:
            record.session.ensure_chat(0)
        return stable_id

    @Slot(str)
    def close_session(self, name: str) -> None:
        """Close the window showing a session, if any.

        Args:
            name: The session name whose window should close.
        """
        record = self._windows.pop(name, None)
        if record is None:
            return
        record.window.close()
        self.windows_changed.emit()
        logger.info("Closed window for session '%s'", name)

    @Slot(str)
    def focus_session(self, name: str) -> None:
        """Raise the window showing a session, if any.

        Args:
            name: The session name to focus.
        """
        record = self._find_window(name)
        if record is not None:
            self._focus(record)

    @Slot()
    def new_window(self) -> None:
        """Create a uniquely named session and open it in a new window."""
        name = self._unique_name("Window")
        self.create_session(name)

    # ------------------------------------------------------------------
    #  Slot: Shared windows
    # ------------------------------------------------------------------

    @Slot()
    def show_editor(self) -> None:
        """Show the shared editor window, creating it on first use."""
        self._editor_window = self._show_tool_window(self._editor_window, _EDITOR_WINDOW_QML)

    @Slot()
    def show_history(self) -> None:
        """Show the shared notification-history window, creating it on first use."""
        self._history_window = self._show_tool_window(
            self._history_window, _HISTORY_WINDOW_QML
        )

    # ------------------------------------------------------------------
    #  Deletion
    # ------------------------------------------------------------------

    def delete_session(self, name: str) -> bool:
        """Delete a session, closing its window, and return whether it existed.

        Args:
            name: The session name to delete.

        Returns:
            ``True`` when the session existed and was deleted.
        """
        if not name or self.app.chat_store.get_session(name) is None:
            return False
        primary_shows = (
            self._primary is not None and self._primary.session.active_session_name == name
        )
        record = self._windows.pop(name, None)
        if record is not None:
            record.session._handle_delete_session(name)
            record.window.close()
        elif primary_shows and self._primary is not None:
            self._primary.session._handle_delete_session(name)
        else:
            self.app.chat_store.delete_session(name)
            self._bus.sessions_changed.emit()
        self.windows_changed.emit()
        logger.info("Deleted session '%s' and closed its window", name)
        return True

    # ------------------------------------------------------------------
    #  Private: Window lifecycle
    # ------------------------------------------------------------------

    def _find_window(self, name: str) -> WindowRecord | None:
        """Return the record for the window showing a session, if any.

        Args:
            name: The session name.

        Returns:
            The matching record, or ``None``.
        """
        if name in self._windows:
            return self._windows[name]
        if self._primary is not None and self._primary.session.active_session_name == name:
            return self._primary
        return None

    def _spawn_window(self, name: str) -> WindowRecord | None:
        """Build controllers and a QML window for a session.

        Args:
            name: The session to show.

        Returns:
            The new window record, or ``None`` when creation fails.
        """
        try:
            context, session, chat, skill = self._factory()
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Failed to build window controllers: %s", error)
            return None

        component = QQmlComponent(self._engine, QUrl.fromLocalFile(str(_WINDOW_QML)))
        created = component.create(context)
        if created is None:
            logger.error("Failed to create ChatWindow.qml: %s", component.errors())
            return None
        window = cast("QWindow", created)
        qwindow = cast("QQuickWindow", created)

        record = WindowRecord(
            session_name=name,
            session=session,
            chat=chat,
            skill=skill,
            window=window,
            context=context,
            component=component,
        )
        session.setParent(window)
        chat.setParent(window)
        skill.setParent(window)

        qwindow.closing.connect(lambda: self._on_window_closing(name))

        try:
            session.open_session(name)
            skill.start()
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Failed to open session '%s' in new window: %s", name, error)

        if self._qt_app is not None:
            record.frame_filter = native_frame.install(self._qt_app, window)

        self._windows[name] = record
        window.show()
        window.requestActivate()
        self.windows_changed.emit()
        logger.info("Opened window for session '%s'", name)
        return record

    def _on_window_closing(self, name: str) -> None:
        """Drop the record when a secondary window closes.

        Args:
            name: The session name whose window is closing.
        """
        record = self._windows.pop(name, None)
        if record is not None:
            record.window.deleteLater()
        self.windows_changed.emit()

    # ------------------------------------------------------------------
    #  Private: Tool windows
    # ------------------------------------------------------------------

    def _show_tool_window(
        self, record: ToolWindowRecord | None, qml_path: Path
    ) -> ToolWindowRecord | None:
        """Show a cached singleton window, creating it on first request.

        Args:
            record: The cached record, or ``None`` when never created.
            qml_path: Path to the window's QML file.

        Returns:
            The shown record, or ``None`` when creation fails.
        """
        if record is None:
            record = self._create_tool_window(qml_path)
            if record is None:
                return None
            self.windows_changed.emit()
            logger.info("Opened tool window: %s", qml_path.name)
        record.window.show()
        record.window.requestActivate()
        return record

    def _create_tool_window(self, qml_path: Path) -> ToolWindowRecord | None:
        """Instantiate a singleton window on the engine root context.

        Args:
            qml_path: Path to the window's QML file.

        Returns:
            The new record, or ``None`` when creation fails.
        """
        component = QQmlComponent(self._engine, QUrl.fromLocalFile(str(qml_path)))
        created = component.create()
        if created is None:
            logger.error("Failed to create %s: %s", qml_path.name, component.errors())
            return None
        return ToolWindowRecord(window=cast("QWindow", created), component=component)

    @staticmethod
    def _focus(record: WindowRecord) -> None:
        """Raise and activate a window.

        Args:
            record: The window to focus.
        """
        record.window.show()
        record.window.requestActivate()
        if hasattr(record.window, "raise_"):
            record.window.raise_()

    def _unique_name(self, base: str) -> str:
        """Return a session name based on *base* that is not already taken.

        Args:
            base: The desired base name.

        Returns:
            A unique session name.
        """
        candidate = base
        suffix = 1
        existing = set(self.app.chat_store.list_sessions())
        while candidate in existing:
            suffix += 1
            candidate = f"{base} {suffix}"
        return candidate
