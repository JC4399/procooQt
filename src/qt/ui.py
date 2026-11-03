"""``ProcooQtUI`` — the UI orchestrator that wires controllers to the QML engine.

Uses composition (not multiple inheritance): the orchestrator owns one controller per
panel and exposes them, plus the backend and theme, as QML context properties. The
``session``, ``chat``, ``skill``, and ``editor`` controllers cover the UI,
with chat rendering and streaming both handled by ``ChatController``.

The primary window's ``session``/``chat``/``skill`` live on the engine's root
context. Secondary windows get a private triple on a child context, built by
:meth:`_build_window_bundle` and managed by :class:`WindowManager` (exposed to
QML as ``windows``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlContext

from .automation_controller import AutomationController
from .chat_controller import ChatController
from .control_controller import ControlController
from .editor_controller import EditorController
from .error_handler import ErrorNotifier
from .notification_controller import NotificationController
from .session_bus import SessionBus
from .session_controller import SessionController
from .skill_controller import SkillController
from .subagent_controller import SubAgentController
from .theme import Theme
from .window_manager import WindowManager

if TYPE_CHECKING:
    from PySide6.QtGui import QWindow
    from PySide6.QtQml import QQmlApplicationEngine

    from ..app import ProcooApp

logger = logging.getLogger("procoo_qt")


class ProcooQtUI(QObject):
    """Top-level UI object exposed to QML as the ``ui`` context property.

    Attributes:
        app: The backend application (config/chat/skill/preset stores).
        engine: The QML application engine.
        theme: The theme registry (also exposed as ``Theme``).
        notifier: Toast/error notifier (also exposed as ``toasts``).
        session_bus: Shared hub broadcasting session-list changes to every window.
        session: Primary window's session group and chat lifecycle controller.
        chat: Primary window's chat rendering and generation controller.
        skill: Primary window's skill tree, tool-mode, and preset controller.
        editor: Code editor and file tree controller.
        automation: Automation page, scheduler, and event-server controller.
        notification: Notification page, badges, and history controller.
        subagent: Headless sub-agent HTTP server controller.
        windows: Manager for primary and secondary per-session windows.
    """

    def __init__(
        self,
        app: ProcooApp,
        engine: QQmlApplicationEngine,
        qt_app: Any = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialise the UI orchestrator and expose it to QML.

        Args:
            app: The backend application holding backend subsystems.
            engine: The QML application engine used for context properties.
            qt_app: The running ``QApplication`` (for native-frame installation
                on secondary windows).
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self.engine = engine
        self.theme = Theme(self)
        self.notifier = ErrorNotifier(self)
        self.session_bus = SessionBus(self)
        self.session = SessionController(app, self.session_bus, self)
        self.chat = ChatController(app, self)
        self.skill = SkillController(app, self)
        self.editor = EditorController(app, self)
        self.automation = AutomationController(app, self)
        self.notification = NotificationController(app, self)
        self.subagent = SubAgentController(app, self)
        self.windows = WindowManager(
            app, engine, self._build_window_bundle, self.session_bus, qt_app, self
        )
        self.control = ControlController(app, self.windows, self)
        self._wire_window(self.session, self.chat, self.skill)
        self._wire_automation()
        self._build_controllers()
        self._expose_to_qml()

    # ------------------------------------------------------------------
    #  Wiring
    # ------------------------------------------------------------------

    def _wire_window(
        self,
        session: SessionController,
        chat: ChatController,
        skill: SkillController,
    ) -> None:
        """Cross-reference and connect one window's controllers.

        Args:
            session: The window's session controller.
            chat: The window's chat controller.
            skill: The window's skill controller.
        """
        chat.session = session
        session.chat = chat
        skill.session = session
        skill.chat = chat
        skill.notifier = self.notifier
        session.toast_requested.connect(self.notifier.toast_requested)
        session.active_chat_changed.connect(chat._handle_chat_activated)
        session.chat_switch_started.connect(chat._handle_chat_switch_started)
        session.active_chat_changed.connect(skill._handle_chat_activated)
        chat.chat_state_changed.connect(session.refresh_chat_panels)
        chat.chat_tokens_changed.connect(session.refresh_chat_tokens)
        chat.config_updated.connect(skill._handle_worker_config_updated)
        chat.toast_requested.connect(self.notifier.toast_requested)
        skill.toast_requested.connect(self.notifier.toast_requested)

    def _wire_automation(self) -> None:
        """Wire automation results, toasts, and editor navigation across controllers."""
        self.skill.skill_files_changed.connect(self.editor._handle_skill_files_changed)
        self.automation.files_changed.connect(self.editor._handle_skill_files_changed)
        self.editor.toast_requested.connect(self.notifier.toast_requested)
        self.editor.editor_open_requested.connect(self.windows.show_editor)
        self.automation.toast_requested.connect(self.notifier.toast_requested)
        self.automation.result_ready.connect(self.notification._handle_automation_result)
        self.automation.edit_automation_requested.connect(self.editor._handle_open_automation)
        self.notification.edit_automation_requested.connect(self.editor._handle_open_automation)

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def _build_controllers(self) -> None:
        """Build every controller's models and state."""
        self.session.build()
        self.chat.build()
        self.skill.build()
        self.editor.build()
        self.notification.build()
        self.automation.build()
        self.control.build()
        self.subagent.build()

    def _build_window_bundle(
        self,
    ) -> tuple[QQmlContext, SessionController, ChatController, SkillController]:
        """Build a fresh controller triple and private context for a new window.

        Returns:
            ``(context, session, chat, skill)`` where *context* is a child of the
            engine root context carrying the window's three controllers.
        """
        session = SessionController(self.app, self.session_bus, self)
        chat = ChatController(self.app, self)
        skill = SkillController(self.app, self)
        session.prewarm_enabled = False
        self._wire_window(session, chat, skill)
        session.build()
        chat.build()
        skill.build()
        context = QQmlContext(self.engine.rootContext())
        context.setContextProperty("session", session)
        context.setContextProperty("chat", chat)
        context.setContextProperty("skill", skill)
        return context, session, chat, skill

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    def start(self, window: QWindow | None = None, frame_filter: Any = None) -> None:
        """Start the UI once the QML root object has loaded.

        Called from ``app.main`` after a successful engine load. Registers the
        primary window with :class:`WindowManager` when *window* is supplied.

        Args:
            window: The primary top-level window.
            frame_filter: The native-frame event filter to keep referenced.
        """
        self.session.start()
        self.skill.start()
        self.editor.start()
        self.automation.start()
        self.control.start()
        self.subagent.start()
        if window is not None:
            self.windows.register_primary(self.session, self.chat, self.skill, window, frame_filter)

    def shutdown(self) -> None:
        """Stop per-chat worker threads before the application exits."""
        self.session.flush_layout()
        self.chat.shutdown()

    # ------------------------------------------------------------------
    #  QML exposure
    # ------------------------------------------------------------------

    def _expose_to_qml(self) -> None:
        """Publish the UI objects to the QML root context."""
        context = self.engine.rootContext()
        context.setContextProperty("ui", self)
        context.setContextProperty("backend", self.app)
        context.setContextProperty("Theme", self.theme)
        context.setContextProperty("toasts", self.notifier)
        context.setContextProperty("session", self.session)
        context.setContextProperty("chat", self.chat)
        context.setContextProperty("skill", self.skill)
        context.setContextProperty("editor", self.editor)
        context.setContextProperty("automation", self.automation)
        context.setContextProperty("notification", self.notification)
        context.setContextProperty("windows", self.windows)
        logger.debug("QML context properties published")
