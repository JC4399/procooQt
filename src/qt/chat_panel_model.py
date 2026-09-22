"""``ChatPanelModel`` — per-panel view model for one chat panel.

Each visible split panel owns one instance. It exposes the panel's active chat,
its tab model, and the runtime state (busy / approval / tokens / loading) that QML
binds to, so up to four panels can render and interact independently.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal

from .models.chat_tab_model import ChatTabModel


class ChatPanelModel(QObject):
    """View model for one chat panel (active chat, tabs, and runtime state)."""

    changed = Signal()

    def __init__(self, index: int, parent: QObject | None = None) -> None:
        """Initialise the panel model.

        Args:
            index: The panel's position in the workspace (0-based).
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self._index = index
        self._active_chat_id = ""
        self._chat_model: QObject | None = None
        self._tab_model = ChatTabModel(self)
        self._busy = False
        self._approval_visible = False
        self._approval_text = ""
        self._input_tokens = 0
        self._output_tokens = 0
        self._loading = False
        self._primary_count = 0
        self._allow_count = 0
        self._ask_count = 0
        self._block_count = 0

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(int, constant=True)
    def panelIndex(self) -> int:  # noqa: N802
        """Return the panel's workspace index."""
        return self._index

    @Property(str, notify=changed)
    def activeChatId(self) -> str:  # noqa: N802
        """Return the panel's active chat id."""
        return self._active_chat_id

    @Property(QObject, notify=changed)
    def chatModel(self) -> QObject | None:  # noqa: N802
        """Return the chat list model for the active chat, or ``None``."""
        return self._chat_model

    @Property(QObject, notify=changed)
    def tabModel(self) -> ChatTabModel:  # noqa: N802
        """Return the panel's chat tab model."""
        return self._tab_model

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        """Return whether the active chat is generating."""
        return self._busy

    @Property(bool, notify=changed)
    def approvalVisible(self) -> bool:  # noqa: N802
        """Return whether the approval bar is shown for the active chat."""
        return self._approval_visible

    @Property(str, notify=changed)
    def approvalText(self) -> str:  # noqa: N802
        """Return the approval prompt text for the active chat."""
        return self._approval_text

    @Property(int, notify=changed)
    def inputTokens(self) -> int:  # noqa: N802
        """Return the active chat's context (input) token count."""
        return self._input_tokens

    @Property(int, notify=changed)
    def outputTokens(self) -> int:  # noqa: N802
        """Return the active chat's cumulative output token count."""
        return self._output_tokens

    @Property(bool, notify=changed)
    def loading(self) -> bool:
        """Return whether the active chat's rebuild overlay is showing."""
        return self._loading

    @Property(int, notify=changed)
    def primaryCount(self) -> int:  # noqa: N802
        """Return the active chat's primary skill count."""
        return self._primary_count

    @Property(int, notify=changed)
    def allowCount(self) -> int:  # noqa: N802
        """Return the active chat's allow-mode tool count."""
        return self._allow_count

    @Property(int, notify=changed)
    def askCount(self) -> int:  # noqa: N802
        """Return the active chat's ask-mode tool count."""
        return self._ask_count

    @Property(int, notify=changed)
    def blockCount(self) -> int:  # noqa: N802
        """Return the active chat's block-mode tool count."""
        return self._block_count

    # ------------------------------------------------------------------
    #  Setters (called by the session controller on the GUI thread)
    # ------------------------------------------------------------------

    def set_panel(
        self,
        active_chat_id: str,
        chat_model: QObject | None,
        tabs: list[dict[str, Any]],
        tabs_active_id: str | None,
        states: dict[str, Any],
    ) -> None:
        """Update the active chat, its model, and the tab rows.

        Args:
            active_chat_id: The panel's active chat id, or an empty string.
            chat_model: The chat list model for the active chat, or ``None``.
            tabs: Enriched chat summaries for this panel's tabs.
            tabs_active_id: The active chat id within the tab model.
            states: Per-chat states used to derive blink flags.
        """
        self._active_chat_id = active_chat_id
        self._chat_model = chat_model
        self._tab_model.set_chats(tabs, tabs_active_id, states)
        self.changed.emit()

    def set_runtime(
        self,
        busy: bool,
        approval_visible: bool,
        approval_text: str,
        input_tokens: int,
        output_tokens: int,
        loading: bool,
        primary_count: int,
        allow_count: int,
        ask_count: int,
        block_count: int,
    ) -> None:
        """Update the runtime display values for the active chat.

        Args:
            busy: Whether the active chat is generating.
            approval_visible: Whether the approval bar is shown.
            approval_text: The approval prompt text.
            input_tokens: Context (input) token count.
            output_tokens: Cumulative output token count.
            loading: Whether the rebuild overlay is showing.
            primary_count: Number of primary skills.
            allow_count: Number of allow-mode tools.
            ask_count: Number of ask-mode tools.
            block_count: Number of block-mode tools.
        """
        self._busy = busy
        self._approval_visible = approval_visible
        self._approval_text = approval_text
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._loading = loading
        self._primary_count = primary_count
        self._allow_count = allow_count
        self._ask_count = ask_count
        self._block_count = block_count
        self.changed.emit()
