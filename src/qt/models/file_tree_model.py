"""``FileTreeModel`` — flattened file/folder tree for ``EditorPanel.qml``.

The skills directory is walked recursively and flattened into one row per visible
entry, tagged with a depth so a QML delegate can indent it. Rows use folder-first
ordering, hidden-name and ``__pycache__`` filtering, and per-folder expand/collapse.
A fuzzy search term filters rows by entry name: a folder whose name matches keeps
its entire subtree, otherwise only matching descendants are shown, and folders
render expanded while a term is active. QML has no matching icon set, so
:attr:`FileRole.ICON` carries a short extension label (``"py"``, ``"md"``, …) or the
folder marker ``"dir"``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models.base import Item, ListModel
from ..qt_roles import FileRole, role_names
from .automation_list_model import fuzzy_match

#: Folder marker shown for directory rows.
FOLDER_ICON = "dir"

#: Fallback label for files whose extension is not in :data:`_EXT_TO_LABEL`.
FILE_ICON = "file"

#: Extension → short label shown for file rows.
_EXT_TO_LABEL: dict[str, str] = {
    ".py": "py",
    ".pyi": "py",
    ".md": "md",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "sh",
    ".bash": "bash",
    ".js": "js",
    ".ts": "ts",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".html": "html",
    ".css": "css",
    ".xml": "xml",
    ".java": "java",
    ".rs": "rs",
    ".go": "go",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "h",
    ".hpp": "hpp",
    ".cs": "cs",
    ".swift": "swift",
    ".kt": "kt",
    ".rb": "rb",
    ".php": "php",
    ".sql": "sql",
    ".dockerfile": "docker",
    ".makefile": "make",
}

#: Names always skipped during the walk.
_SKIPPED_NAMES = {"__pycache__"}


class FileTreeModel(ListModel):
    """Flattened (depth-tagged) file tree model with fuzzy search and expand/collapse.

    Attributes:
        roles: File role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the file tree model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(FileRole), parent)
        self._root: Path | None = None
        self._search: str = ""
        self._expanded: set[str] = set()

    # ------------------------------------------------------------------
    #  Public: structure
    # ------------------------------------------------------------------

    def rebuild(self, root: Path | str, search: str = "") -> None:
        """Walk ``root`` and replace all rows, preserving collapse state.

        Args:
            root: The skills directory to flatten.
            search: Optional fuzzy term filtering the rows by entry name.
        """
        self._root = Path(root)
        self._search = (search or "").strip()
        self._flatten()

    def set_search(self, search: str) -> None:
        """Set the fuzzy search term and re-flatten the rows.

        Args:
            search: The new search term (``""`` clears the filter).
        """
        self._search = (search or "").strip()
        self._flatten()

    def set_folder_expanded(self, path: str, expanded: bool) -> None:
        """Record a folder's collapse state and re-flatten the rows.

        Args:
            path: The folder's path relative to the root.
            expanded: ``True`` to show the folder's children.
        """
        if expanded:
            self._expanded.add(path)
        else:
            self._expanded.discard(path)
        self._flatten()

    def is_folder_expanded(self, path: str) -> bool:
        """Return whether a folder's children are currently shown.

        Folders start collapsed; while a search term is active every folder
        renders expanded so matches and matched subtrees stay visible.

        Args:
            path: The folder's path relative to the root.

        Returns:
            ``True`` if the folder is expanded or a search term is active.
        """
        return bool(self._search) or path in self._expanded

    # ------------------------------------------------------------------
    #  Private: flattening
    # ------------------------------------------------------------------

    def _flatten(self) -> None:
        """Rebuild all rows from the stored root, search term, and collapse state."""
        rows: list[Item] = []
        keys: list[str] = []
        if self._root is not None:
            if self._search:
                self._walk_search(self._root, 0, "", rows, keys)
            else:
                self._walk(self._root, 0, "", rows, keys)
        self.set_items(rows, keys)

    def _walk(
        self,
        directory: Path,
        depth: int,
        parent_path: str,
        rows: list[Item],
        keys: list[str],
    ) -> None:
        """Append rows for one directory, recursing into expanded folders.

        Used when no search term is active.

        Args:
            directory: The directory to read.
            depth: Nesting depth used for indentation.
            parent_path: Accumulated path relative to the root.
            rows: Row accumulator.
            keys: Identity-key accumulator.
        """
        for entry in self._sorted_entries(directory):
            if self._is_hidden(entry):
                continue
            path = self._join(parent_path, entry.name)
            if entry.is_dir():
                rows.append(self._folder_row(path, entry.name, depth))
                keys.append(f"folder:{path}")
                if self.is_folder_expanded(path):
                    self._walk(entry, depth + 1, path, rows, keys)
            else:
                rows.append(self._file_row(path, entry.name, depth))
                keys.append(f"file:{path}")

    def _walk_search(
        self,
        directory: Path,
        depth: int,
        parent_path: str,
        rows: list[Item],
        keys: list[str],
    ) -> bool:
        """Append the rows of one directory that survive the fuzzy search filter.

        A folder whose name matches keeps its entire subtree (via
        :meth:`_walk_all`); otherwise the folder is kept only when a descendant
        matches, showing just the matching chain.

        Args:
            directory: The directory to read.
            depth: Nesting depth used for indentation.
            parent_path: Accumulated path relative to the root.
            rows: Row accumulator.
            keys: Identity-key accumulator.

        Returns:
            ``True`` when any entry under ``directory`` matched the search term.
        """
        matched = False
        for entry in self._sorted_entries(directory):
            if self._is_hidden(entry):
                continue
            path = self._join(parent_path, entry.name)
            if entry.is_dir():
                if self._matches(entry.name):
                    rows.append(self._folder_row(path, entry.name, depth))
                    keys.append(f"folder:{path}")
                    self._walk_all(entry, depth + 1, path, rows, keys)
                    matched = True
                    continue
                child_rows: list[Item] = []
                child_keys: list[str] = []
                if self._walk_search(entry, depth + 1, path, child_rows, child_keys):
                    rows.append(self._folder_row(path, entry.name, depth))
                    keys.append(f"folder:{path}")
                    rows.extend(child_rows)
                    keys.extend(child_keys)
                    matched = True
            elif self._matches(entry.name):
                rows.append(self._file_row(path, entry.name, depth))
                keys.append(f"file:{path}")
                matched = True
        return matched

    def _walk_all(
        self,
        directory: Path,
        depth: int,
        parent_path: str,
        rows: list[Item],
        keys: list[str],
    ) -> None:
        """Append every row under ``directory``, ignoring the collapse state.

        Used beneath a folder whose name matched the search term: the whole
        subtree stays visible regardless of the user's expand/collapse state.

        Args:
            directory: The directory to read.
            depth: Nesting depth used for indentation.
            parent_path: Accumulated path relative to the root.
            rows: Row accumulator.
            keys: Identity-key accumulator.
        """
        for entry in self._sorted_entries(directory):
            if self._is_hidden(entry):
                continue
            path = self._join(parent_path, entry.name)
            if entry.is_dir():
                rows.append(self._folder_row(path, entry.name, depth))
                keys.append(f"folder:{path}")
                self._walk_all(entry, depth + 1, path, rows, keys)
            else:
                rows.append(self._file_row(path, entry.name, depth))
                keys.append(f"file:{path}")

    # ------------------------------------------------------------------
    #  Private: rows
    # ------------------------------------------------------------------

    @staticmethod
    def _folder_row(path: str, name: str, depth: int) -> Item:
        """Build a folder row.

        Args:
            path: Folder path relative to the root.
            name: Folder display name.
            depth: Nesting depth.

        Returns:
            A role-keyed folder row.
        """
        return {
            int(FileRole.PATH): path,
            int(FileRole.NAME): name,
            int(FileRole.DEPTH): depth,
            int(FileRole.IS_FOLDER): True,
            int(FileRole.ICON): FOLDER_ICON,
        }

    @staticmethod
    def _file_row(path: str, name: str, depth: int) -> Item:
        """Build a file row.

        Args:
            path: File path relative to the root.
            name: File display name.
            depth: Nesting depth.

        Returns:
            A role-keyed file row.
        """
        return {
            int(FileRole.PATH): path,
            int(FileRole.NAME): name,
            int(FileRole.DEPTH): depth,
            int(FileRole.IS_FOLDER): False,
            int(FileRole.ICON): _EXT_TO_LABEL.get(Path(name).suffix.lower(), FILE_ICON),
        }

    # ------------------------------------------------------------------
    #  Private: helpers
    # ------------------------------------------------------------------

    def _matches(self, name: str) -> bool:
        """Return whether a display name passes the active fuzzy filter.

        Args:
            name: The entry's display name.

        Returns:
            ``True`` when there is no search term or the term is a
            case-insensitive in-order subsequence of the name.
        """
        return fuzzy_match(self._search, name)

    @staticmethod
    def _sorted_entries(directory: Path) -> list[Path]:
        """Return a directory's entries in visible order (folders first, A→Z).

        Args:
            directory: The directory to read.

        Returns:
            The sorted entries, or an empty list when it cannot be read.
        """
        try:
            return sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except (OSError, PermissionError):
            return []

    @staticmethod
    def _join(parent_path: str, name: str) -> str:
        """Join a child name onto its parent's root-relative path.

        Args:
            parent_path: The parent folder path relative to the root.
            name: The child entry's display name.

        Returns:
            The child's path relative to the root.
        """
        return f"{parent_path}/{name}" if parent_path else name

    @staticmethod
    def _is_hidden(entry: Path) -> bool:
        """Return whether an entry is filtered out of the tree.

        Skips names beginning with ``"."`` (except ``".gitignore"``) and the
        ``__pycache__`` directory.

        Args:
            entry: The directory entry to test.

        Returns:
            ``True`` when the entry should be hidden.
        """
        if entry.name in _SKIPPED_NAMES:
            return True
        return entry.name.startswith(".") and entry.name != ".gitignore"
