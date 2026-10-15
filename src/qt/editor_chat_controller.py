"""``EditorChatController`` — full chat panel beside the code editor.

The editor chat is a **real chat** managed by
:class:`~src.qt.chat_controller.ChatController` (chat id ``"editor-chat"``), so it
renders with the same streaming cards, tool cards, token counts, and approval
workflow as a workspace panel.  This controller is a thin façade: it creates a
private chat record, registers the chat as always-visible (its model is drawn in
the editor window rather than a panel), injects the open file as context before
each turn, and exposes the per-chat state to QML.

The chat record uses a private session name so it never appears in the session
selector or workspace panels.  Its skills/tools are copied from the active chat
with all tool modes forced to ``allow`` because the editor has no approval bar.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..chat.manager import chat_manager
from .chat_worker import remove_worker
from .error_handler import TOAST_ERROR

if TYPE_CHECKING:
    from ..app import ProcooApp
    from .chat_controller import ChatController
    from .editor_controller import EditorController
    from .models.chat_list_model import ChatListModel
    from .session_controller import SessionController

logger = logging.getLogger("procoo_qt")

#: Chat id backing the editor conversation in ``chat_manager``/``ChatStore``.
EDITOR_CHAT_ID = "editor-chat"

#: Private session name so the editor chat stays out of the session UI.
EDITOR_SESSION = "__editor__"

#: Maximum characters of the open file injected as context.
MAX_CONTEXT_CHARS = 8000


class EditorChatController(QObject):
    """Façade exposing a full :class:`ChatController` chat to the editor panel."""

    state_changed = Signal()
    toast_requested = Signal(str, str)

    if TYPE_CHECKING:
        # Attributes provided by ui.py orchestrator
        app: ProcooApp

        # Attributes owned by this controller
        _chat_id: str
        _last_context_key: str
        _tasks: set[asyncio.Task[Any]]

        # Attributes provided by other controllers (composition)
        chat: ChatController
        editor: EditorController
        session: SessionController

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the editor chat controller.

        Args:
            app: The top-level application holding backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._tasks: set[asyncio.Task[Any]] = set()

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Create the private chat, register it visible, and expose its model."""
        self._chat_id = EDITOR_CHAT_ID
        self._last_context_key = ""
        self._ensure_chat_record()
        self.chat.add_visible_chat(self._chat_id)
        self._refresh()

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=state_changed)
    def chat_model(self) -> ChatListModel:
        """Return the editor chat's render model.

        Returns:
            The ``ChatListModel`` exposed to QML as ``editorChat.chat_model``.
        """
        return self.chat.model_for(self._chat_id)

    @Property(bool, notify=state_changed)
    def busy(self) -> bool:
        """Return whether the editor chat is generating."""
        return self._state().is_busy

    @Property(bool, notify=state_changed)
    def approvalVisible(self) -> bool:  # noqa: N802
        """Return whether a tool call awaits approval."""
        return bool(self._state().pending_tool_info)

    @Property(str, notify=state_changed)
    def approvalText(self) -> str:  # noqa: N802
        """Return the pending approval prompt text."""
        return self._state().approval_text

    @Property(int, notify=state_changed)
    def inputTokens(self) -> int:  # noqa: N802
        """Return the editor chat's context token count."""
        return self._state().true_input_tokens

    @Property(int, notify=state_changed)
    def outputTokens(self) -> int:  # noqa: N802
        """Return the editor chat's cumulative output tokens."""
        return self._state().true_output_cum

    @Property(str, notify=state_changed)
    def modelName(self) -> str:  # noqa: N802
        """Return the editor chat's model name."""
        state = self._state()
        return state.model_name or self.app.config.llm_model_name

    @Property(int, notify=state_changed)
    def primaryCount(self) -> int:  # noqa: N802
        """Return the editor chat's primary skill count."""
        return self._state().primary_count

    @Property(int, notify=state_changed)
    def allowCount(self) -> int:  # noqa: N802
        """Return the editor chat's allow-mode tool count."""
        return self._state().allow_count

    @Property(int, notify=state_changed)
    def askCount(self) -> int:  # noqa: N802
        """Return the editor chat's ask-mode tool count."""
        return self._state().ask_count

    @Property(int, notify=state_changed)
    def blockCount(self) -> int:  # noqa: N802
        """Return the editor chat's block-mode tool count."""
        return self._state().block_count

    # ------------------------------------------------------------------
    #  Slot: Send / stop / clear
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_send(self, text: str) -> None:
        """Send a message through the editor chat.

        Args:
            text: The user message.
        """
        message = (text or "").strip()
        if not message:
            return
        if self._state().is_busy:
            self.toast_requested.emit("Please wait for the current response.", TOAST_ERROR)
            return
        self._spawn(self._send(message))

    async def _send(self, message: str) -> None:
        """Inject file context, then launch the shared chat generation.

        Args:
            message: The user message to send.
        """
        try:
            self._ensure_chat_record()
            agent = await self.session._hydrate_chat(self._chat_id)
            if agent is None:
                return
            context = self._file_context()
            worker = self.chat.attach_worker(self._chat_id, agent)
            if context:
                worker.append_message({"role": "system", "content": context})
            self.chat._handle_send_for(self._chat_id, message)
        finally:
            self._refresh()

    @Slot()
    def _handle_stop(self) -> None:
        """Stop the editor chat's current generation."""
        self.chat._handle_stop_for(self._chat_id)
        self._refresh()

    @Slot()
    def _handle_regenerate(self) -> None:
        """Regenerate the editor chat's last user message."""
        self.chat._handle_regenerate_for(self._chat_id)
        self._refresh()

    @Slot(int)
    def _handle_delete_turn(self, msg_index: int) -> None:
        """Delete the editor chat turn containing a card.

        Args:
            msg_index: Index of the source message in the editor chat history.
        """
        self.chat._handle_delete_turn_for(self._chat_id, msg_index)
        self._refresh()

    @Slot(int)
    def _handle_regenerate_from(self, msg_index: int) -> None:
        """Regenerate the editor chat from a specific user card.

        Args:
            msg_index: Index of the source user message in the editor chat.
        """
        self.chat._handle_regenerate_from_for(self._chat_id, msg_index)
        self._refresh()

    @Slot()
    def _handle_clear(self) -> None:
        """Discard the editor conversation and start fresh."""
        self.chat._handle_stop_for(self._chat_id)
        remove_worker(self._chat_id)
        chat_manager.remove_chat(self._chat_id)
        stored = self.app.chat_store.load_chat(self._chat_id) or {"id": self._chat_id}
        stored["messages"] = []
        stored["message_count"] = 0
        stored["true_input_tokens"] = 0
        stored["true_output_cum"] = 0
        stored["skills_config"] = self._active_skill_config()
        self.app.chat_store.save_chat(self._chat_id, stored)
        state = self._state()
        state.true_input_tokens = 0
        state.true_output_cum = 0
        state.message_count = 0
        self.chat.model_for(self._chat_id).clear()
        self._last_context_key = ""
        self._refresh()

    # ------------------------------------------------------------------
    #  Slot: State refresh
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_state_changed(self, chat_id: str) -> None:
        """Refresh properties when the editor chat's state changes.

        Args:
            chat_id: The chat whose state changed.
        """
        if chat_id == self._chat_id:
            self.state_changed.emit()

    @Slot(int, int)
    def _handle_token_counts(self, input_tokens: int, output_tokens: int) -> None:
        """Refresh the token readout.

        Args:
            input_tokens: Context token count (ignored; state is authoritative).
            output_tokens: Output token count (ignored; state is authoritative).
        """
        self.state_changed.emit()

    # ------------------------------------------------------------------
    #  Chat record / skills
    # ------------------------------------------------------------------

    def _ensure_chat_record(self) -> None:
        """Create the private chat record if missing, or refresh its config.

        While the live agent has not yet been built, the stored skills/tool
        configuration is refreshed from the active chat so the editor chat
        follows the user's current selection.
        """
        existing = self.app.chat_store.load_chat(self._chat_id)
        if existing is None:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            self.app.chat_store.save_chat(
                self._chat_id,
                {
                    "id": self._chat_id,
                    "skills_config": self._active_skill_config(),
                    "messages": [],
                    "session": EDITOR_SESSION,
                    "created_at": now,
                    "updated_at": now,
                    "message_count": 0,
                    "model_name": self.app.config.llm_model_name,
                    "true_input_tokens": 0,
                    "true_output_cum": 0,
                },
            )
            return
        if chat_manager.get_chat(self._chat_id) is None and not existing.get("messages"):
            existing["skills_config"] = self._active_skill_config()
            self.app.chat_store.save_chat(self._chat_id, existing)

    def _active_skill_config(self) -> dict[str, Any]:
        """Build a skills/tool config from the active chat, tools forced allow.

        Returns:
            A ``{"primary", "secondary", "tools"}`` config dict.
        """
        primary: list[str] = []
        secondary: list[str] = []
        chat_id = getattr(self.session, "active_chat_id", "") if self.session else ""
        if chat_id:
            stored = self.app.chat_store.load_chat(chat_id) or {}
            config = stored.get("skills_config", {})
            primary = list(config.get("primary", []) or [])
            secondary = list(config.get("secondary", []) or [])
        tool_defs = self.app.skill_manager.load_tool_functions(primary)
        tools = {td["name"]: "allow" for td in tool_defs}
        return {"primary": primary, "secondary": secondary, "tools": tools}

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _state(self) -> Any:
        """Return the editor chat's UI state (creating it on demand)."""
        return self.session.state(self._chat_id)

    def _file_context(self) -> str:
        """Build a system context block for the currently open file.

        The block is produced only when the open file or its content changed
        since the last injection, to avoid bloating the conversation.

        Returns:
            The context block, or an empty string when nothing changed.
        """
        path = getattr(getattr(self, "editor", None), "currentFile", "") or ""
        if not path:
            return ""
        text = getattr(self.editor, "currentText", "") or ""
        key = f"{path}:{hash(text)}"
        if key == self._last_context_key:
            return ""
        self._last_context_key = key
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError:
            content = text
        return f"[Editor context]\nOpen file: {path}\n\n```\n{content[:MAX_CONTEXT_CHARS]}\n```"

    def _refresh(self) -> None:
        """Notify QML that the editor chat state changed."""
        self.state_changed.emit()

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Schedule a coroutine and keep a reference until it completes.

        Args:
            coro: The coroutine to schedule on the running event loop.
        """
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        task.add_done_callback(self._log_task_failure)

    @staticmethod
    def _log_task_failure(task: asyncio.Task[Any]) -> None:
        """Log an unexpected background task failure.

        Args:
            task: The completed task.
        """
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("Editor chat background task failed: %s", error)
