"""Notification manager — in-memory history with unread tracking.

Results from the scheduler and the event server are converted into
:class:`NotificationItem` objects here.  Success runs become ``log``
notifications (auto-acknowledged when the notification page opens), while
``info`` and ``error`` notifications stay unread until the user confirms them.

The manager is deliberately Qt-free: the Qt controller calls these methods and
emits the UI signals.  State is persisted to ``storage/notifications.json`` on
every mutation.
"""

from __future__ import annotations

import logging
import time
import uuid

from ..automation.models import AutomationResult, AutomationResultKind
from .models import NotificationItem, NotificationKind
from .store import NotificationStore

logger = logging.getLogger("procoo_qt")

_RESULT_KIND: dict[AutomationResultKind, NotificationKind] = {
    AutomationResultKind.SUCCESS: NotificationKind.LOG,
    AutomationResultKind.INFO: NotificationKind.INFO,
    AutomationResultKind.ERROR: NotificationKind.ERROR,
}


class NotificationManager:
    """Stores automation notifications and tracks per-kind unread counts.

    Attributes:
        items: All notifications, newest first.
    """

    def __init__(self, storage_dir: str) -> None:
        """Initialise the manager and load persisted notifications.

        Args:
            storage_dir: Root storage directory.
        """
        self._store = NotificationStore(storage_dir)
        self.items: list[NotificationItem] = self._load()

    # ------------------------------------------------------------------
    #  Public: Add / lookup
    # ------------------------------------------------------------------

    def add(self, result: AutomationResult) -> NotificationItem:
        """Convert an automation result into a notification and persist it.

        Args:
            result: The completed automation result.

        Returns:
            The newly created notification (inserted at the front).
        """
        item = NotificationItem(
            id=uuid.uuid4().hex,
            kind=_RESULT_KIND.get(result.kind, NotificationKind.ERROR),
            task=result.task,
            path=result.path,
            message=result.message,
            log=result.log,
            data=result.data,
            timestamp=result.timestamp or time.strftime("%Y-%m-%d %H:%M:%S"),
            read=False,
        )
        self.items.insert(0, item)
        self._persist()
        logger.info("Notification added: %s (%s)", item.task, item.kind)
        return item

    def get(self, item_id: str) -> NotificationItem | None:
        """Return a notification by id, or ``None``."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    # ------------------------------------------------------------------
    #  Public: Unread counts / marking
    # ------------------------------------------------------------------

    def unread_counts(self) -> dict[NotificationKind, int]:
        """Return the number of unread notifications per kind.

        Returns:
            Mapping of every kind to its unread count (zeros included).
        """
        counts = dict.fromkeys(NotificationKind, 0)
        for item in self.items:
            if not item.read:
                counts[item.kind] += 1
        return counts

    def mark_logs_read(self) -> list[str]:
        """Mark every unread ``log`` notification as read.

        Returns:
            The ids of the notifications that changed (empty when none did).
        """
        changed: list[str] = []
        for item in self.items:
            if item.kind == NotificationKind.LOG and not item.read:
                item.read = True
                changed.append(item.id)
        if changed:
            self._persist()
        return changed

    def mark_read(self, item_id: str) -> bool:
        """Mark a single notification as read (e.g. on Confirm).

        Args:
            item_id: The notification to acknowledge.

        Returns:
            ``True`` when the item existed and changed.
        """
        item = self.get(item_id)
        if item is None or item.read:
            return False
        item.read = True
        self._persist()
        return True

    # ------------------------------------------------------------------
    #  Public: History
    # ------------------------------------------------------------------

    def history(
        self, *, offset: int = 0, limit: int = 20, search: str = ""
    ) -> list[NotificationItem]:
        """Return a page of notifications, newest first.

        Args:
            offset: Number of matching notifications to skip.
            limit: Maximum number of notifications to return.
            search: Case-insensitive filter over task name and message.

        Returns:
            The page of matching notifications.
        """
        filtered = self._filter(search)
        return filtered[offset : offset + limit]

    def total(self, search: str = "") -> int:
        """Return the number of notifications matching a search string.

        Args:
            search: Case-insensitive filter over task name and message (empty = all).

        Returns:
            The match count.
        """
        return len(self._filter(search))

    # ------------------------------------------------------------------
    #  Private
    # ------------------------------------------------------------------

    def _filter(self, search: str) -> list[NotificationItem]:
        """Return notifications whose task or message matches *search*."""
        needle = search.strip().casefold()
        if not needle:
            return list(self.items)
        return [
            item
            for item in self.items
            if needle in item.task.casefold() or needle in item.message.casefold()
        ]

    def _load(self) -> list[NotificationItem]:
        """Load persisted notifications, skipping malformed rows."""
        items: list[NotificationItem] = []
        for row in self._store.load():
            try:
                items.append(NotificationItem.model_validate(row))
            except Exception as error:
                logger.warning("Skipping malformed notification: %s", error)
        return items

    def _persist(self) -> None:
        """Persist all notifications as plain dicts."""
        self._store.save([item.model_dump() for item in self.items])
