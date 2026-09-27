"""``NotificationController`` — notification cards, unread badges, and history.

Owns the bell page model, the per-kind unread counts shown as title-bar badges,
read semantics (success logs auto-read when the page opens; info/error on
Confirm), the Debug action that opens the source automation, and the searchable,
paged history window.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..notification.models import NotificationKind
from .models.notification_list_model import NotificationListModel

if TYPE_CHECKING:
    from ..app import ProcooApp
    from ..automation.models import AutomationResult

logger = logging.getLogger("procoo_qt")

#: Notifications loaded per history page.
HISTORY_PAGE_SIZE = 20


class NotificationController(QObject):
    """Notification page and history controller."""

    notifications_changed = Signal()
    counts_changed = Signal()
    history_changed = Signal()
    edit_automation_requested = Signal(str)

    if TYPE_CHECKING:
        # Attributes provided by ui.py orchestrator
        app: ProcooApp

        # Attributes owned by this controller
        _model: NotificationListModel
        _history_model: NotificationListModel
        _history_offset: int
        _history_total: int
        _history_search: str

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the notification controller.

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
        """Build the page and history models from persisted notifications."""
        self._model = NotificationListModel(self)
        self._history_model = NotificationListModel(self)
        self._history_offset = 0
        self._history_total = 0
        self._history_search = ""
        self._rebuild_page()
        self._reload_history()

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=notifications_changed)
    def notification_model(self) -> NotificationListModel:
        """Return the bell-page notification model.

        Returns:
            The model exposed to QML as ``notification.notification_model``.
        """
        return self._model

    @Property(QObject, notify=history_changed)
    def history_model(self) -> NotificationListModel:
        """Return the history notification model.

        Returns:
            The model exposed to QML as ``notification.history_model``.
        """
        return self._history_model

    @Property(int, notify=counts_changed)
    def logCount(self) -> int:  # noqa: N802
        """Return the number of unread success logs (grey badge)."""
        return self._unread(NotificationKind.LOG)

    @Property(int, notify=counts_changed)
    def infoCount(self) -> int:  # noqa: N802
        """Return the number of unread info notifications (amber badge)."""
        return self._unread(NotificationKind.INFO)

    @Property(int, notify=counts_changed)
    def errorCount(self) -> int:  # noqa: N802
        """Return the number of unread error notifications (red badge)."""
        return self._unread(NotificationKind.ERROR)

    @Property(str, notify=history_changed)
    def historySearch(self) -> str:  # noqa: N802
        """Return the active history search term."""
        return self._history_search

    @Property(bool, notify=history_changed)
    def historyExhausted(self) -> bool:  # noqa: N802
        """Return whether all matching history notifications are loaded."""
        return self._history_offset >= self._history_total

    # ------------------------------------------------------------------
    #  Slot: Automation result
    # ------------------------------------------------------------------

    @Slot(object)
    def _handle_automation_result(self, result: AutomationResult) -> None:
        """Store a new automation result and refresh the views.

        Args:
            result: The completed automation result.
        """
        self.app.notification_manager.add(result)
        self._rebuild_page()
        self._reload_history()
        self.counts_changed.emit()

    # ------------------------------------------------------------------
    #  Slot: Page open / read marking
    # ------------------------------------------------------------------

    @Slot()
    def _handle_page_opened(self) -> None:
        """Mark success logs read when the notification page is opened."""
        if self.app.notification_manager.mark_logs_read():
            self._rebuild_page()
            self._reload_history()
            self.counts_changed.emit()

    @Slot(str)
    def _handle_confirm(self, item_id: str) -> None:
        """Acknowledge an info or error notification.

        Args:
            item_id: The notification to mark read.
        """
        if self.app.notification_manager.mark_read(item_id):
            self._rebuild_page()
            self._reload_history()
            self.counts_changed.emit()

    # ------------------------------------------------------------------
    #  Slot: Debug
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_debug(self, item_id: str) -> None:
        """Open the source automation of a failed notification.

        Args:
            item_id: The notification whose automation should be opened.
        """
        item = self.app.notification_manager.get(item_id)
        if item is not None:
            self.edit_automation_requested.emit(item.path)

    # ------------------------------------------------------------------
    #  Slot: History
    # ------------------------------------------------------------------

    @Slot()
    def _handle_view_history(self) -> None:
        """Reset the history search and reload the first page."""
        self._history_search = ""
        self._history_offset = 0
        self._reload_history()

    @Slot(str)
    def _handle_history_search(self, text: str) -> None:
        """Filter the history list.

        Args:
            text: The search term.
        """
        self._history_search = (text or "").strip()
        self._history_offset = 0
        self._reload_history()

    @Slot()
    def _handle_load_more(self) -> None:
        """Append the next history page (called when scrolled to the bottom)."""
        if self._history_offset >= self._history_total:
            return
        rows = self.app.notification_manager.history(
            offset=self._history_offset,
            limit=HISTORY_PAGE_SIZE,
            search=self._history_search,
        )
        self._history_model.append_notifications(rows)
        self._history_offset += len(rows)
        self.history_changed.emit()

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _unread(self, kind: NotificationKind) -> int:
        """Return the unread count for one notification kind."""
        return self.app.notification_manager.unread_counts().get(kind, 0)

    def _rebuild_page(self) -> None:
        """Rebuild the bell-page model from all notifications."""
        self._model.set_notifications(self.app.notification_manager.items)
        self.notifications_changed.emit()

    def _reload_history(self) -> None:
        """Reload the first history page for the active search term."""
        rows = self.app.notification_manager.history(
            offset=0, limit=HISTORY_PAGE_SIZE, search=self._history_search
        )
        self._history_model.set_notifications(rows)
        self._history_offset = len(rows)
        self._history_total = self.app.notification_manager.total(self._history_search)
        self.history_changed.emit()
