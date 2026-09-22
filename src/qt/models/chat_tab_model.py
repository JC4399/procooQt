"""``ChatTabModel`` — chat tabs rendered by ``ChatTabBar.qml`` for one panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.base import Item, ListModel
from ..qt_roles import ChatTabRole, role_names

if TYPE_CHECKING:
    from ..chat_state import ChatState


class ChatTabModel(ListModel):
    """List model of chat tabs for a single chat panel.

    Rows are built from enriched chat summaries (already filtered to the panel's
    chats and ordered). Chat summaries must be pre-enriched by the controller
    with ``title`` and ``status`` keys.

    Attributes:
        roles: Chat tab role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the chat tab model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(ChatTabRole), parent)

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def set_chats(
        self,
        chats: list[dict[str, Any]],
        active_id: str | None,
        states: dict[str, ChatState],
    ) -> None:
        """Replace rows with the given chats.

        Args:
            chats: Enriched chat summary dicts in tab order.
            active_id: The currently active chat id, or ``None``.
            states: Per-chat states used to derive the blink flag.
        """
        rows: list[Item] = []
        keys: list[str] = []
        for chat in chats:
            chat_id = str(chat.get("id", ""))
            state = states.get(chat_id)
            blinking = bool(state and state.is_busy and not state.pending_tool_info)
            rows.append(
                {
                    int(ChatTabRole.CHAT_ID): chat_id,
                    int(ChatTabRole.TITLE): chat.get("title", chat_id[:15]),
                    int(ChatTabRole.STATUS): chat.get("status", ""),
                    int(ChatTabRole.IS_ACTIVE): chat_id == active_id,
                    int(ChatTabRole.IS_BLINKING): blinking,
                    int(ChatTabRole.MESSAGE_COUNT): chat.get("message_count", 0),
                }
            )
            keys.append(f"chat:{chat_id}")
        self.set_items(rows, keys)
