"""Reusable ``QAbstractListModel`` base driving QML ``ListView`` delegates.

Concrete models declare their roles as an ``IntEnum`` and store each row as a plain
``dict`` keyed by role id. This keeps the Python side free of Qt item classes while
still giving QML typed role access.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Slot,
)

ParentIndex = QModelIndex | QPersistentModelIndex
Item = dict[int, Any]


class ListModel(QAbstractListModel):
    """A simple list model over role-keyed dictionaries.

    Attributes:
        roles: Mapping of role id to UTF-8 role name.
    """

    def __init__(self, roles: dict[int, bytes], parent: Any = None) -> None:
        """Initialise the model.

        Args:
            roles: Mapping of role id to UTF-8 role name.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.roles = roles
        self._items: list[Item] = []
        self._keys: list[str] = []

    # ------------------------------------------------------------------
    #  QAbstractListModel overrides
    # ------------------------------------------------------------------

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        """Return the QML role-name mapping.

        Returns:
            Mapping of role id to role name.
        """
        return {role_id: QByteArray(name) for role_id, name in self.roles.items()}

    def rowCount(self, parent: ParentIndex = QModelIndex()) -> int:  # noqa: N802, B008
        """Return the number of rows.

        Args:
            parent: Parent index (always invalid for a list model).

        Returns:
            Row count.
        """
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: ParentIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return the role value for a row.

        Args:
            index: The row index.
            role: The requested role id.

        Returns:
            The stored value, or ``None`` if unavailable.
        """
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        return self._items[index.row()].get(role)

    # ------------------------------------------------------------------
    #  Public: mutation
    # ------------------------------------------------------------------

    def set_items(self, items: list[Item], keys: list[str] | None = None) -> None:
        """Replace all rows with ``items``.

        Args:
            items: The new list of role-keyed rows.
            keys: Optional per-row identity keys used by :meth:`diff_update`.
                Defaults to empty keys, which makes every row unique.
        """
        if keys is None:
            keys = [""] * len(items)
        self.beginResetModel()
        self._items = list(items)
        self._keys = list(keys)
        self.endResetModel()

    def diff_update(self, items: list[Item], keys: list[str]) -> int:
        """Incrementally align rows to ``items`` using per-row identity keys.

        Rows whose key matches the existing row at the same index are left
        untouched; the first mismatching index and everything after it is
        removed and re-inserted.

        Args:
            items: The new list of role-keyed rows.
            keys: Per-row identity keys, one per item (e.g. content hashes).

        Returns:
            The divergence index, or ``-1`` if the model was already up to date.

        Raises:
            ValueError: If ``keys`` and ``items`` differ in length.
        """
        if len(keys) != len(items):
            raise ValueError("keys length must match items length")
        divergence = self.find_divergence(keys)
        if divergence < 0:
            return -1
        if divergence < len(self._items):
            self.beginRemoveRows(QModelIndex(), divergence, len(self._items) - 1)
            del self._items[divergence:]
            del self._keys[divergence:]
            self.endRemoveRows()
        if divergence < len(items):
            self.beginInsertRows(QModelIndex(), divergence, len(items) - 1)
            self._items.extend(items[divergence:])
            self._keys.extend(keys[divergence:])
            self.endInsertRows()
        return divergence

    def find_divergence(self, keys: list[str]) -> int:
        """Return the first index at which ``keys`` differs from stored keys.

        Args:
            keys: The candidate per-row identity keys.

        Returns:
            The first differing index, or ``-1`` if identical.
        """
        for index, key in enumerate(keys):
            if index >= len(self._keys) or self._keys[index] != key:
                return index
        if len(self._keys) > len(keys):
            return len(keys)
        return -1

    def append_item(self, item: Item, key: str = "") -> int:
        """Append a single row.

        Args:
            item: The role-keyed row to append.
            key: The row's identity key.

        Returns:
            The index of the appended row.
        """
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self._keys.append(key)
        self.endInsertRows()
        return row

    def update_item(self, row: int, values: Item) -> None:
        """Merge ``values`` into an existing row and notify QML.

        Args:
            row: The row index to update.
            values: Role-keyed values to merge.
        """
        if not 0 <= row < len(self._items):
            return
        self._items[row].update(values)
        top_left = self.index(row, 0)
        self.dataChanged.emit(top_left, top_left, list(values.keys()))

    def clear(self) -> None:
        """Remove all rows."""
        self.set_items([])

    # ------------------------------------------------------------------
    #  Slots: QML access
    # ------------------------------------------------------------------

    @Slot(int, result="QVariantMap")
    def get(self, row: int) -> dict[str, Any]:
        """Return a row as a string-keyed map for QML.

        Args:
            row: The row index.

        Returns:
            The role-keyed row, or an empty map if out of range.
        """
        if 0 <= row < len(self._items):
            return {str(role): value for role, value in self._items[row].items()}
        return {}

    @Slot(result=int)
    def count(self) -> int:
        """Return the number of rows.

        Returns:
            Row count.
        """
        return len(self._items)
