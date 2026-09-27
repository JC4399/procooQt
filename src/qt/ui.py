"""``ProcooQtUI`` — the UI orchestrator that wires controllers to the QML engine.

Uses composition (not multiple inheritance): the orchestrator owns one controller per
panel and exposes them, plus the backend and theme, as QML context properties. The
``session``, ``chat``, ``skill``, and ``editor`` controllers cover the UI,
with chat rendering and streaming both handled by ``ChatController``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot

from .automation_controller import AutomationController
from .chat_controller import ChatController
from .editor_chat_controller import EditorChatController
from .editor_controller import EditorController
from .error_handler import ErrorNotifier
from .notification_controller import NotificationController
from .session_controller import SessionController
from .skill_controller import SkillController
from .theme import Theme

if TYPE_CHECKING:
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
        session: Session group and chat lifecycle controller.
        chat: Chat rendering and generation controller.
        skill: Skill tree, tool-mode, and preset controller.
        editor: Code editor and file tree controller.
        editor_chat: Chat panel controller embedded in the editor window.
        automation: Automation page, scheduler, and event-server controller.
        notification: Notification page, badges, and history controller.
    """

    def __init__(
        self,
        app: ProcooApp,
        engine: QQmlApplicationEngine,
        parent: QObject | None = None,
    ) -> None:
        """Initialise the UI orchestrator and expose it to QML.

        Args:
            app: The backend application holding backend subsystems.
            engine: The QML application engine used for context properties.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self.engine = engine
        self.theme = Theme(self)
        self.notifier = ErrorNotifier(self)
        self.session = SessionController(app, self)
        self.chat = ChatController(app, self)
        self.skill = SkillController(app, self)
        self.editor = EditorController(app, self)
        self.editor_chat = EditorChatController(app, self)
        self.automation = AutomationController(app, self)
        self.notification = NotificationController(app, self)
        self.chat.session = self.session
        self.session.chat = self.chat
        self.skill.session = self.session
        self.skill.chat = self.chat
        self.skill.notifier = self.notifier
        self.editor_chat.editor = self.editor
        self.editor_chat.session = self.session
        self.editor_chat.chat = self.chat
        self.session.toast_requested.connect(self.notifier.toast_requested)
        self.session.active_chat_changed.connect(self.chat._handle_chat_activated)
        self.session.chat_switch_started.connect(self.chat._handle_chat_switch_started)
        self.session.active_chat_changed.connect(self.skill._handle_chat_activated)
        self.chat.chat_state_changed.connect(self.session.refresh_chat_panels)
        self.chat.chat_state_changed.connect(self.editor_chat._handle_state_changed)
        self.chat.token_counts_changed.connect(self.editor_chat._handle_token_counts)
        self.skill.skill_files_changed.connect(self.editor._handle_skill_files_changed)
        self.automation.files_changed.connect(self.editor._handle_skill_files_changed)
        self.chat.toast_requested.connect(self.notifier.toast_requested)
        self.skill.toast_requested.connect(self.notifier.toast_requested)
        self.editor.toast_requested.connect(self.notifier.toast_requested)
        self.editor_chat.toast_requested.connect(self.notifier.toast_requested)
        self.automation.toast_requested.connect(self.notifier.toast_requested)
        self.automation.result_ready.connect(self.notification._handle_automation_result)
        self.automation.edit_automation_requested.connect(self.editor._handle_open_automation)
        self.notification.edit_automation_requested.connect(self.editor._handle_open_automation)
        self._build_controllers()
        self._expose_to_qml()

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def _build_controllers(self) -> None:
        """Build every controller's models and state."""
        self.session.build()
        self.chat.build()
        self.skill.build()
        self.editor.build()
        self.editor_chat.build()
        self.notification.build()
        self.automation.build()

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Start the UI once the QML root object has loaded.

        Called from ``app.main`` after a successful engine load. Future parts
        hook their own startup here (P3 chat restore, P6 skill watcher).
        """
        self.session.start()
        self.skill.start()
        self.editor.start()
        self.automation.start()

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
        context.setContextProperty("editorChat", self.editor_chat)
        context.setContextProperty("automation", self.automation)
        context.setContextProperty("notification", self.notification)
        logger.debug("QML context properties published")
