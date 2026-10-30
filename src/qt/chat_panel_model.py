"""``ChatPanelModel`` — per-panel view model for one chat panel.

Each visible split panel owns one instance. It exposes the panel's active chat,
its tab model, and the runtime state (busy / approval / tokens / loading) that QML
binds to, so up to four panels can render and interact independently.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from .models.chat_tab_model import ChatTabModel
from .models.transcript_list_model import TranscriptListModel


class ChatPanelModel(QObject):
    """View model for one chat panel (active chat, tabs, and runtime state)."""

    active_chat_changed = Signal()
    chat_model_changed = Signal()
    runtime_changed = Signal()
    transcripts_changed = Signal()

    def __init__(self, index: int, parent: QObject | None = None) -> None:
        """Initialise the panel model.

        Args:
            index: The panel's fixed slot id in the workspace (0-based).
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self._index = index
        self._active_chat_id = ""
        self._chat_model: QObject | None = None
        self._tab_model = ChatTabModel(self)
        self._transcript_model = TranscriptListModel(self)
        self._model_provider: Callable[[str], QObject] | None = None
        self._busy = False
        self._approval_visible = False
        self._approval_text = ""
        self._input_tokens = 0
        self._output_tokens = 0
        self._loading = False
        self._activated_count = 0
        self._allow_count = 0
        self._ask_count = 0
        self._block_count = 0
        self._model_name = ""

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(int, constant=True)
    def panelIndex(self) -> int:  # noqa: N802
        """Return the panel's fixed workspace slot id."""
        return self._index

    @Property(str, notify=active_chat_changed)
    def activeChatId(self) -> str:  # noqa: N802
        """Return the panel's active chat id."""
        return self._active_chat_id

    @Property(QObject, notify=chat_model_changed)
    def chatModel(self) -> QObject | None:  # noqa: N802
        """Return the chat list model for the active chat, or ``None``."""
        return self._chat_model

    @Property(QObject, constant=True)
    def tabModel(self) -> ChatTabModel:  # noqa: N802
        """Return the panel's chat tab model."""
        return self._tab_model

    @Property(QObject, constant=True)
    def transcriptModel(self) -> TranscriptListModel:  # noqa: N802
        """Return the model of chat ids that own a live transcript view."""
        return self._transcript_model

    @Property(bool, notify=runtime_changed)
    def busy(self) -> bool:
        """Return whether the active chat is generating."""
        return self._busy

    @Property(bool, notify=runtime_changed)
    def approvalVisible(self) -> bool:  # noqa: N802
        """Return whether the approval bar is shown for the active chat."""
        return self._approval_visible

    @Property(str, notify=runtime_changed)
    def approvalText(self) -> str:  # noqa: N802
        """Return the approval prompt text for the active chat."""
        return self._approval_text

    @Property(int, notify=runtime_changed)
    def inputTokens(self) -> int:  # noqa: N802
        """Return the active chat's context (input) token count."""
        return self._input_tokens

    @Property(int, notify=runtime_changed)
    def outputTokens(self) -> int:  # noqa: N802
        """Return the active chat's cumulative output token count."""
        return self._output_tokens

    @Property(bool, notify=runtime_changed)
    def loading(self) -> bool:
        """Return whether the active chat's rebuild overlay is showing."""
        return self._loading

    @Property(int, notify=runtime_changed)
    def activatedCount(self) -> int:  # noqa: N802
        """Return the active chat's activated skill count."""
        return self._activated_count

    @Property(int, notify=runtime_changed)
    def allowCount(self) -> int:  # noqa: N802
        """Return the active chat's allow-mode tool count."""
        return self._allow_count

    @Property(int, notify=runtime_changed)
    def askCount(self) -> int:  # noqa: N802
        """Return the active chat's ask-mode tool count."""
        return self._ask_count

    @Property(int, notify=runtime_changed)
    def blockCount(self) -> int:  # noqa: N802
        """Return the active chat's block-mode tool count."""
        return self._block_count

    @Property(str, notify=runtime_changed)
    def modelName(self) -> str:  # noqa: N802
        """Return the LLM model name selected for the active chat."""
        return self._model_name

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

        Only emits when the active chat or its model actually changed; the tab
        model self-dedupes, so re-pushing an unchanged panel is a no-op.

        Args:
            active_chat_id: The panel's active chat id, or an empty string.
            chat_model: The chat list model for the active chat, or ``None``.
            tabs: Enriched chat summaries for this panel's tabs.
            tabs_active_id: The active chat id within the tab model.
            states: Per-chat states used to derive blink flags.
        """
        active_changed = self._active_chat_id != active_chat_id
        model_changed = self._chat_model is not chat_model
        self._active_chat_id = active_chat_id
        self._chat_model = chat_model
        self._tab_model.set_chats(tabs, tabs_active_id, states)
        if active_changed:
            self.active_chat_changed.emit()
        if model_changed:
            self.chat_model_changed.emit()

    def update_tab(self, chat_id: str, status: str, blinking: bool) -> None:
        """Update one tab's status/blink without rebuilding the panel.

        Args:
            chat_id: The chat whose tab to update.
            status: The new :class:`ChatStatus` string.
            blinking: Whether the tab dot should pulse.
        """
        self._tab_model.update_chat(chat_id, status, blinking)

    def set_model_provider(self, provider: Callable[[str], QObject]) -> None:
        """Set the callable used to resolve a chat id to its list model.

        Args:
            provider: A callable returning the stable ``ChatListModel`` for a
                chat id (creating it on demand).
        """
        self._model_provider = provider

    def set_transcripts(self, chat_ids: list[str]) -> None:
        """Update which chats keep a live transcript view.

        Args:
            chat_ids: Chat ids that should have a live transcript, in order.
        """
        self._transcript_model.set_ids(chat_ids)

    @Slot(str, result=QObject)
    def chatModelFor(self, chat_id: str) -> QObject | None:  # noqa: N802
        """Return the stable chat list model for a chat id.

        Args:
            chat_id: The chat whose model to return.

        Returns:
            The chat's ``ChatListModel``, or ``None`` when no provider is set.
        """
        if self._model_provider is None:
            return None
        return self._model_provider(chat_id)

    def set_runtime(
        self,
        busy: bool,
        approval_visible: bool,
        approval_text: str,
        input_tokens: int,
        output_tokens: int,
        loading: bool,
        activated_count: int,
        allow_count: int,
        ask_count: int,
        block_count: int,
        model_name: str,
    ) -> None:
        """Update the runtime display values for the active chat.

        Emits ``runtime_changed`` only when at least one value differs, so an
        untouched panel is not invalidated by another panel's refresh.

        Args:
            busy: Whether the active chat is generating.
            approval_visible: Whether the approval bar is shown.
            approval_text: The approval prompt text.
            input_tokens: Context (input) token count.
            output_tokens: Cumulative output token count.
            loading: Whether the rebuild overlay is showing.
            activated_count: Number of activated skills.
            allow_count: Number of allow-mode tools.
            ask_count: Number of ask-mode tools.
            block_count: Number of block-mode tools.
            model_name: LLM model name selected for the active chat.
        """
        if (
            self._busy == busy
            and self._approval_visible == approval_visible
            and self._approval_text == approval_text
            and self._input_tokens == input_tokens
            and self._output_tokens == output_tokens
            and self._loading == loading
            and self._activated_count == activated_count
            and self._allow_count == allow_count
            and self._ask_count == ask_count
            and self._block_count == block_count
            and self._model_name == model_name
        ):
            return
        self._busy = busy
        self._approval_visible = approval_visible
        self._approval_text = approval_text
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._loading = loading
        self._activated_count = activated_count
        self._allow_count = allow_count
        self._ask_count = ask_count
        self._block_count = block_count
        self._model_name = model_name
        self.runtime_changed.emit()

    def set_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Update only the active chat's token counts.

        Used for the per-round ``token_usage`` refresh so the token bar updates
        live without rebuilding the rest of the runtime state.

        Args:
            input_tokens: Context (input) token count.
            output_tokens: Cumulative output token count.
        """
        if self._input_tokens == input_tokens and self._output_tokens == output_tokens:
            return
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.runtime_changed.emit()
