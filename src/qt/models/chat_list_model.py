"""``ChatListModel`` — rendered chat items (user/thinking/response/tool/result)."""

from __future__ import annotations

from typing import Any

from ..models.base import Item, ListModel
from ..qt_roles import ChatRole, role_names


class ChatListModel(ListModel):
    """Incremental list model of chat items for one chat.

    Attributes:
        roles: Chat role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the chat list model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(ChatRole), parent)

    # ------------------------------------------------------------------
    #  Public: row lookup and replacement
    # ------------------------------------------------------------------

    def find_pending_result(self, tool_call_id: str) -> int:
        """Return the row of a pending tool-result card for a tool call.

        Args:
            tool_call_id: The tool-call id stored on the pending card.

        Returns:
            The row index, or ``-1`` if no matching pending card exists.
        """
        for row, item in enumerate(self._items):
            if not item.get(int(ChatRole.IS_PENDING)):
                continue
            if item.get(int(ChatRole.TOOL_CALL_ID)) == tool_call_id:
                return row
        return -1

    def replace_item(self, row: int, item: Item, key: str) -> None:
        """Replace one row and its identity key in place.

        Args:
            row: The row index to replace.
            item: The new role-keyed row.
            key: The new identity key used by :meth:`diff_update`.
        """
        if not 0 <= row < len(self._items):
            return
        self._items[row] = item
        self._keys[row] = key
        top_left = self.index(row, 0)
        self.dataChanged.emit(top_left, top_left, list(item.keys()))
