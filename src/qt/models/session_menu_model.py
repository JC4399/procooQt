"""``SessionMenuModel`` — session rows for the title-bar session selector."""

from __future__ import annotations

from typing import Any

from ..models.base import Item, ListModel
from ..qt_roles import SessionMenuRole, role_names


class SessionMenuModel(ListModel):
    """List model of sessions with a trailing "add session" row.

    The final row is always the synthetic ``+`` row (:attr:`SessionMenuRole.IS_ADD`),
    so it stays visible even when ``Default`` is the only session.

    Attributes:
        roles: Session menu role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the session menu model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(SessionMenuRole), parent)

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def set_sessions(self, names: list[str], active_name: str | None) -> None:
        """Replace rows with the session names plus a trailing add row.

        Args:
            names: Session names in display order.
            active_name: The currently active session name, or ``None``.
        """
        rows: list[Item] = []
        keys: list[str] = []
        for name in names:
            rows.append(
                {
                    int(SessionMenuRole.NAME): name,
                    int(SessionMenuRole.IS_ADD): False,
                    int(SessionMenuRole.IS_ACTIVE): name == active_name,
                }
            )
            keys.append(f"session:{name}")
        rows.append(
            {
                int(SessionMenuRole.NAME): "+",
                int(SessionMenuRole.IS_ADD): True,
                int(SessionMenuRole.IS_ACTIVE): False,
            }
        )
        keys.append("session:+")
        self.set_items(rows, keys)
