"""``EditorController`` — code editor, file tree, and syntax highlighter.

Owns the file tree model and the editor state. Behavior ports from
``src/flet/editor_panel.py``: a read-only code editor with a collapsible file tree
rooted at the skills directory, plus Edit/Save/Cancel/Reload. File reads and writes are
offloaded with :func:`asyncio.to_thread` so the qasync loop never blocks.

The skill watcher drives realtime reconciliation: while the editor window is showing,
directory changes rebuild the file tree and the open file is compared with disk. A
deleted or externally modified open file raises :attr:`file_conflict` for the QML layer
to prompt the user (keep the buffer vs. take the on-disk state).

The :class:`CodeHighlighter` attaches to the QML ``TextArea`` through its
``textDocument`` property (see :meth:`attachHighlighter`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QTextDocument

from .error_handler import TOAST_ERROR, TOAST_INFO, TOAST_WARNING
from .highlighter import CodeHighlighter
from .models.file_tree_model import FileTreeModel

if TYPE_CHECKING:
    from ..app import ProcooApp

logger = logging.getLogger("procoo_qt")

#: Extension → language name passed to :class:`CodeHighlighter`. Mirrors the Flet
#: ``_EXT_TO_LANGUAGE`` map; unsupported extensions normalise to ``"plain"``.
_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "plain",
    ".sh": "bash",
    ".bash": "bash",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".html": "html",
    ".xml": "html",
    ".css": "css",
    ".sql": "sql",
    ".java": "plain",
    ".rs": "plain",
    ".go": "plain",
    ".cpp": "plain",
    ".c": "plain",
    ".h": "plain",
    ".hpp": "plain",
    ".cs": "plain",
    ".swift": "plain",
    ".kt": "plain",
    ".rb": "plain",
    ".php": "plain",
    ".dockerfile": "plain",
    ".makefile": "plain",
}


def detect_language(filepath: str) -> str:
    """Detect a highlighter language from a file path's suffix.

    Args:
        filepath: The file path to inspect.

    Returns:
        The language name, or ``"plain"`` when the extension is unknown.
    """
    return _EXT_TO_LANGUAGE.get(Path(filepath).suffix.lower(), "plain")


class EditorController(QObject):
    """Code editor and file tree controller."""

    file_tree_changed = Signal()
    current_file_changed = Signal(str)
    edit_mode_changed = Signal(bool)
    file_conflict = Signal(str, str)
    toast_requested = Signal(str, str)

    if TYPE_CHECKING:
        # Attributes provided by ui.py orchestrator
        app: ProcooApp

        # Attributes owned by this controller
        _file_model: FileTreeModel
        _current_path: str | None
        _current_text: str
        _language: str
        _is_editing: bool
        _active: bool
        _disk_mtime: float | None
        _conflict_path: str | None
        _conflict_kind: str
        _conflict_mtime: float
        _highlighter: CodeHighlighter | None
        _document: QTextDocument | None
        _document_wrapper: Any | None
        _tasks: set[asyncio.Task[Any]]

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the editor controller.

        Args:
            app: The top-level application holding backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the file tree model and initialise the editor state."""
        self._file_model = FileTreeModel(self)
        self._current_path = None
        self._current_text = ""
        self._language = "plain"
        self._is_editing = False
        self._active = False
        self._disk_mtime = None
        self._conflict_path = None
        self._conflict_kind = ""
        self._conflict_mtime = 0.0
        self._highlighter = None
        self._document = None
        self._document_wrapper = None
        self._tasks = set()
        self._refresh_file_tree()

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=file_tree_changed)
    def file_model(self) -> FileTreeModel:
        """Return the flattened file tree model.

        Returns:
            The model exposed to QML as ``editor.file_model``.
        """
        return self._file_model

    @Property(str, notify=current_file_changed)
    def currentFile(self) -> str:  # noqa: N802
        """Return the path of the file open in the editor.

        Returns:
            The current file path, or an empty string.
        """
        return self._current_path or ""

    @Property(str, notify=current_file_changed)
    def currentText(self) -> str:  # noqa: N802
        """Return the editor buffer.

        Returns:
            The last loaded or saved file content.
        """
        return self._current_text

    @currentText.setter
    def currentText(self, value: str) -> None:  # noqa: N802
        self._current_text = value or ""
        self.current_file_changed.emit(self.currentFile)

    @Property(bool, notify=edit_mode_changed)
    def editing(self) -> bool:
        """Return whether the editor is in edit mode.

        Returns:
            ``True`` while the user may modify the buffer.
        """
        return self._is_editing

    @Property(str, notify=current_file_changed)
    def language(self) -> str:
        """Return the active highlighter language.

        Returns:
            The language name for the current file.
        """
        return self._language

    # ------------------------------------------------------------------
    #  Slot: Start
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """(Re)build the file tree from the skills directory."""
        self._refresh_file_tree()

    # ------------------------------------------------------------------
    #  Slot: Window visibility
    # ------------------------------------------------------------------

    @Slot(bool)
    def _handle_window_visibility(self, visible: bool) -> None:
        """Track editor-window visibility and re-sync when it becomes visible.

        Hidden windows skip watcher reconciliation entirely so no conflict prompt
        is raised off-screen; showing the window triggers a full refresh (and
        re-raises any conflict that was left pending).

        Args:
            visible: Whether the editor window is currently showing.
        """
        self._active = visible
        if not visible:
            return
        if self._conflict_path is not None:
            self.file_conflict.emit(self._conflict_kind, self._conflict_path)
            return
        self._spawn(self._refresh_from_watcher())

    # ------------------------------------------------------------------
    #  Slot: Watcher refresh
    # ------------------------------------------------------------------

    @Slot()
    def _handle_skill_files_changed(self) -> None:
        """Reconcile the editor after a skill-directory change (GUI thread).

        A no-op while the editor window is hidden; the tree and open file are
        re-synchronised when the window is next shown.
        """
        if not self._active:
            return
        self._spawn(self._refresh_from_watcher())

    async def _refresh_from_watcher(self) -> None:
        """Rebuild the file tree off-loop, then reconcile the open file."""
        try:
            await asyncio.to_thread(self._file_model.rebuild, self.app.skill_manager.skills_dir)
        except Exception as error:
            logger.error("Editor tree refresh failed: %s", error)
            return
        self.file_tree_changed.emit()
        await self._reload_open_file_if_changed()

    async def _reload_open_file_if_changed(self) -> None:
        """Compare the open file with disk and prompt on a conflict.

        Raises :attr:`file_conflict` for a deleted or externally modified open
        file. The prompt is suppressed while a conflict is already pending, and
        re-reads that match the buffer only update the known disk mtime.
        """
        path = self._current_path
        if not path or self._conflict_path is not None:
            return
        try:
            stat = await asyncio.to_thread(Path(path).stat)
        except OSError:
            self._open_conflict("deleted", path, 0.0)
            return
        mtime = stat.st_mtime
        if self._disk_mtime is not None and mtime == self._disk_mtime:
            return
        try:
            content = await asyncio.to_thread(Path(path).read_text, encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("Editor reconcile read failed for %s: %s", path, exc)
            return
        if content == self._current_text:
            self._disk_mtime = mtime
            return
        self._open_conflict("modified", path, mtime)

    def _open_conflict(self, kind: str, path: str, mtime: float) -> None:
        """Record a pending file conflict and ask QML to prompt.

        Args:
            kind: Either ``"deleted"`` or ``"modified"``.
            path: The conflicted file path.
            mtime: The external modification time (``0.0`` when deleted).
        """
        self._conflict_kind = kind
        self._conflict_path = path
        self._conflict_mtime = mtime
        logger.warning("Editor conflict (%s): %s", kind, path)
        self.file_conflict.emit(kind, path)

    # ------------------------------------------------------------------
    #  Slot: Conflict resolution
    # ------------------------------------------------------------------

    @Slot()
    def _handle_conflict_keep(self) -> None:
        """Resolve a conflict by keeping the editor buffer.

        A deleted file is recreated from the buffer; an externally modified file
        keeps the buffer and records the new disk mtime so it is not re-prompted
        until the file changes again.
        """
        kind = self._conflict_kind
        if kind == "deleted":
            self._spawn(self._save(self._current_text))
        elif kind == "modified":
            self._disk_mtime = self._conflict_mtime
        self._clear_conflict()

    @Slot()
    def _handle_conflict_discard(self) -> None:
        """Resolve a conflict by taking the on-disk state.

        A deleted file is closed in the editor; an externally modified file is
        reloaded from disk (leaving edit mode first).
        """
        kind = self._conflict_kind
        path = self._conflict_path
        self._clear_conflict()
        if kind == "deleted":
            self._set_editing(False)
            self._current_path = None
            self._current_text = ""
            self._language = "plain"
            if self._highlighter is not None:
                self._highlighter.set_language(self._language)
            self.current_file_changed.emit("")
        elif kind == "modified" and path:
            self._set_editing(False)
            self._spawn(self._load_file_into_editor(path))

    def _clear_conflict(self) -> None:
        """Clear the pending conflict state."""
        self._conflict_path = None
        self._conflict_kind = ""
        self._conflict_mtime = 0.0

    # ------------------------------------------------------------------
    #  Slot: File click
    # ------------------------------------------------------------------

    @Slot(str, bool)
    def _handle_file_click(self, path: str, is_folder: bool) -> None:
        """Open a file or toggle a folder in the file tree.

        Args:
            path: The entry path relative to the skills root.
            is_folder: Whether the clicked row is a folder.
        """
        if is_folder:
            expanded = not self._file_model.is_folder_expanded(path)
            self._handle_folder_toggle(path, expanded)
            return
        self._open_file_in_editor(str(Path(self.app.skill_manager.skills_dir) / path))

    # ------------------------------------------------------------------
    #  Slot: Folder toggle
    # ------------------------------------------------------------------

    @Slot(str, bool)
    def _handle_folder_toggle(self, path: str, expanded: bool) -> None:
        """Expand or collapse a folder and refresh the tree.

        Args:
            path: The folder path relative to the skills root.
            expanded: Whether the folder should be expanded.
        """
        self._file_model.set_folder_expanded(path, expanded)
        self.file_tree_changed.emit()

    @Slot(str, result=bool)
    def isFolderExpanded(self, path: str) -> bool:  # noqa: N802
        """Return whether a folder row is expanded (used by the QML delegate).

        Args:
            path: The folder path relative to the skills root.

        Returns:
            ``True`` when the folder's children are shown.
        """
        return self._file_model.is_folder_expanded(path)

    # ------------------------------------------------------------------
    #  Slot: Edit / Save / Cancel / Reload
    # ------------------------------------------------------------------

    @Slot()
    def _handle_edit(self) -> None:
        """Enter edit mode, warning when no file is open."""
        if not self._current_path:
            self.toast_requested.emit("Select a file first.", TOAST_WARNING)
            return
        self._set_editing(True)

    @Slot(str)
    def _handle_save(self, text: str) -> None:
        """Write the QML editor buffer to the current file.

        Args:
            text: The buffer contents passed from the QML ``TextArea``.
        """
        if not self._current_path:
            self.toast_requested.emit("Select a file first.", TOAST_WARNING)
            return
        self._spawn(self._save(text))

    @Slot()
    def _handle_cancel(self) -> None:
        """Revert the buffer from disk and exit edit mode."""
        if not self._current_path:
            return
        self._set_editing(False)
        self._spawn(self._load_file_into_editor(self._current_path))

    @Slot()
    def _handle_reload(self) -> None:
        """Re-read the current file from disk and leave edit mode."""
        if not self._current_path:
            self.toast_requested.emit("Select a file first.", TOAST_WARNING)
            return
        self._set_editing(False)
        self._spawn(self._load_file_into_editor(self._current_path))

    # ------------------------------------------------------------------
    #  Slot: Highlighter bridge
    # ------------------------------------------------------------------

    @Slot(QObject)
    def attachHighlighter(self, area: QObject) -> None:  # noqa: N802
        """Attach a :class:`CodeHighlighter` to a QML ``TextArea``.

        QML passes the ``TextArea``; its ``textDocument`` property is a
        ``QQuickTextDocument`` wrapper whose :meth:`textDocument` returns the
        ``QTextDocument`` a ``QSyntaxHighlighter`` needs. Both the wrapper and the
        document are retained: the wrapper owns the document, so dropping it would
        delete the C++ object out from under the highlighter. Missing documents are
        ignored and never raise.

        Args:
            area: The QML ``TextArea`` control.
        """
        wrapper = self._text_document_wrapper(area)
        if wrapper is None:
            return
        obtain = getattr(wrapper, "textDocument", None)
        if not callable(obtain):
            logger.warning("Highlighter not attached: no text document available")
            return
        document = obtain()
        if document is None:
            logger.warning("Highlighter not attached: empty text document")
            return
        self._document_wrapper = wrapper
        self._document = document
        self._highlighter = CodeHighlighter(document)
        self._highlighter.set_language(self._language)

    @staticmethod
    def _text_document_wrapper(area: QObject) -> Any | None:
        """Read a QML control's ``textDocument`` property defensively.

        Args:
            area: The QML control exposing a ``textDocument`` property.

        Returns:
            The ``QQuickTextDocument`` wrapper, or ``None`` when unavailable.
        """
        try:
            return area.property("textDocument")
        except Exception:
            logger.warning("Highlighter not attached: textDocument unavailable")
            return None

    # ------------------------------------------------------------------
    #  State: open / load / save
    # ------------------------------------------------------------------

    def _open_file_in_editor(self, filepath: str) -> None:
        """Load ``filepath`` into the editor, blocking while an edit is active.

        Args:
            filepath: Absolute path to the file to open.
        """
        if self._is_editing:
            self.toast_requested.emit("Save or cancel the current edit first.", TOAST_WARNING)
            return
        self._spawn(self._load_file_into_editor(filepath))

    async def _load_file_into_editor(self, filepath: str) -> None:
        """Read a file off the loop and update the editor state.

        Args:
            filepath: Absolute path to the file to load.
        """
        try:
            content, mtime = await asyncio.to_thread(self._read_file, filepath)
        except (OSError, UnicodeDecodeError) as exc:
            logger.error("Failed to read %s: %s", filepath, exc)
            self.toast_requested.emit(f"Failed to read file: {exc}", TOAST_ERROR)
            return

        self._current_path = filepath
        self._current_text = content
        self._disk_mtime = mtime
        self._language = detect_language(filepath)
        if self._highlighter is not None:
            self._highlighter.set_language(self._language)
        logger.debug("Opened %s (%s)", filepath, self._language)
        self.current_file_changed.emit(filepath)

    async def _save(self, text: str) -> None:
        """Write ``text`` to the current file off the loop.

        Args:
            text: The buffer contents to persist.
        """
        path = self._current_path
        if not path:
            return
        try:
            mtime = await asyncio.to_thread(self._write_file, path, text)
        except OSError as exc:
            logger.error("Failed to save %s: %s", path, exc)
            self.toast_requested.emit(f"Failed to save file: {exc}", TOAST_ERROR)
            return

        logger.info("Saved editor content to %s", path)
        self._current_text = text
        self._disk_mtime = mtime
        self._set_editing(False)
        self.toast_requested.emit(f"Saved {Path(path).name}.", TOAST_INFO)
        self.current_file_changed.emit(path)

    # ------------------------------------------------------------------
    #  State: edit mode
    # ------------------------------------------------------------------

    def _set_editing(self, editing: bool) -> None:
        """Set the edit flag and notify QML when it changes.

        Args:
            editing: The new edit-mode state.
        """
        if self._is_editing == editing:
            return
        self._is_editing = editing
        self.edit_mode_changed.emit(editing)

    # ------------------------------------------------------------------
    #  State: file tree
    # ------------------------------------------------------------------

    def _refresh_file_tree(self) -> None:
        """Rebuild the file tree from the skills directory."""
        self._file_model.rebuild(self.app.skill_manager.skills_dir)
        self.file_tree_changed.emit()

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file(path: str) -> tuple[str, float]:
        """Read a file and its modification time (blocking).

        Args:
            path: Absolute path to read.

        Returns:
            Tuple of file content and ``st_mtime``.

        Raises:
            OSError: When the file cannot be read.
            UnicodeDecodeError: When the file is not valid UTF-8.
        """
        file = Path(path)
        return file.read_text(encoding="utf-8"), file.stat().st_mtime

    @staticmethod
    def _write_file(path: str, text: str) -> float:
        """Write text to a file and return its modification time (blocking).

        Args:
            path: Absolute path to write.
            text: Content to persist.

        Returns:
            The file's ``st_mtime`` after the write.

        Raises:
            OSError: When the file cannot be written.
        """
        file = Path(path)
        file.write_text(text, encoding="utf-8")
        return file.stat().st_mtime

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
            logger.error("Editor background task failed: %s", error)
