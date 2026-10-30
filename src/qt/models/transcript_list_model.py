"""``TranscriptListModel`` — chat ids that currently own a live transcript view.

The workspace keeps one rendered :class:`~src.qml.panels.ChatTranscript` per chat
so switching tabs only toggles visibility instead of rebuilding delegates. This
model tells QML which transcripts to keep alive. It is incremental so adding,
removing, or moving an id does not destroy the delegates of the ids that remain.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex

from ..models.base import ListModel
from ..qt_roles import TranscriptRole, role_names


class TranscriptListModel(ListModel):
    """Incremental list of chat ids with a live transcript view.

    Attributes:
        roles: Transcript role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the transcript list model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(TranscriptRole), parent)

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def _ids(self) -> list[str]:
        """Return the current chat ids in row order."""
        role = int(TranscriptRole.CHAT_ID)
        return [str(item.get(role, "")) for item in self._items]

    def set_ids(self, chat_ids: list[str]) -> None:
        """Replace the live transcript ids.

        Removes ids that disappeared and inserts new ids at their target
        positions, so ids that stay keep their delegate (and its rich-text
        layout). This matters when a chat moves between panels: the old panel
        loses one row and the new panel gains one, without resetting either
        model.

        Args:
            chat_ids: Chat ids that should have a live transcript, in order.
        """
        if self._ids() == chat_ids:
            return

        role = int(TranscriptRole.CHAT_ID)
        wanted = set(chat_ids)

        for index in range(len(self._items) - 1, -1, -1):
            if self._items[index].get(role, "") in wanted:
                continue
            self.beginRemoveRows(QModelIndex(), index, index)
            del self._items[index]
            del self._keys[index]
            self.endRemoveRows()

        current = self._ids()
        for index, chat_id in enumerate(chat_ids):
            if index < len(current) and current[index] == chat_id:
                continue
            if chat_id in current[index:]:
                old_index = current.index(chat_id, index)
                self.beginRemoveRows(QModelIndex(), old_index, old_index)
                del self._items[old_index]
                del self._keys[old_index]
                self.endRemoveRows()
                current.pop(old_index)
            self.beginInsertRows(QModelIndex(), index, index)
            self._items.insert(index, {role: chat_id})
            self._keys.insert(index, chat_id)
            self.endInsertRows()
            current.insert(index, chat_id)
