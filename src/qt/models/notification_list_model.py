"""``NotificationListModel`` — notification cards for the bell page and history.

Rows are role-keyed dictionaries exposing the notification id (for Confirm),
kind (for card colouring), task, message, log, timestamp, read flag, and the
source automation path (for the Debug action).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.base import Item, ListModel
from ..qt_roles import NotificationRole, role_names

if TYPE_CHECKING:
    from ...notification.models import NotificationItem


class NotificationListModel(ListModel):
    """List model of notification cards.

    Attributes:
        roles: Notification role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the notification model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(NotificationRole), parent)

    # ------------------------------------------------------------------
    #  Builders
    # ------------------------------------------------------------------

    def set_notifications(self, items: list[NotificationItem]) -> None:
        """Replace all rows with *items*.

        Args:
            items: Notifications, newest first.
        """
        rows = [self.row(item) for item in items]
        keys = [f"notification:{item.id}" for item in items]
        self.set_items(rows, keys)

    def append_notifications(self, items: list[NotificationItem]) -> None:
        """Append rows for *items* (used for history "load more").

        Args:
            items: Additional notifications to append.
        """
        rows = [self.row(item) for item in items]
        keys = [f"notification:{item.id}" for item in items]
        self.append_items(rows, keys)

    @staticmethod
    def row(item: NotificationItem) -> Item:
        """Build a role-keyed notification row.

        Args:
            item: The notification to flatten.

        Returns:
            A role-keyed row consumed by the QML delegate.
        """
        return {
            int(NotificationRole.ID): item.id,
            int(NotificationRole.KIND): item.kind.value,
            int(NotificationRole.TASK): item.task,
            int(NotificationRole.MESSAGE): item.message,
            int(NotificationRole.LOG): item.log,
            int(NotificationRole.TIMESTAMP): item.timestamp,
            int(NotificationRole.READ): item.read,
            int(NotificationRole.PATH): item.path,
        }
