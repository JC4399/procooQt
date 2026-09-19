"""``FileTreeModel`` — flattened file/folder tree for ``EditorPanel.qml``.

The skills directory is walked recursively and flattened into one row per visible
entry, tagged with a depth so a QML delegate can indent it. Ports the Flet builder
(``_build_tree_nodes`` / ``_build_folder_node`` / ``_build_file_node``): folder-first
ordering, hidden-name and ``__pycache__`` filtering, and per-folder expand/collapse.
QML has no matching icon set, so :attr:`FileRole.ICON` carries a short extension label
(``"py"``, ``"md"``, …) or the folder marker ``"dir"``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models.base import Item, ListModel
from ..qt_roles import FileRole, role_names

#: Folder marker shown for directory rows.
FOLDER_ICON = "dir"

#: Fallback label for files whose extension is not in :data:`_EXT_TO_LABEL`.
FILE_ICON = "file"

#: Extension → short label. Mirrors the extension set of the Flet ``_EXT_TO_LANGUAGE``
#: map (and its sibling ``_EXT_TO_ICON``).
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
    """Flattened (depth-tagged) file tree model with folder expand/collapse.

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
        self._expanded: set[str] = set()

    # ------------------------------------------------------------------
    #  Public: structure
    # ------------------------------------------------------------------

    def rebuild(self, root: Path | str) -> None:
        """Walk ``root`` and replace all rows, preserving collapse state.

        Args:
            root: The skills directory to flatten.
        """
        self._root = Path(root)
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

        Folders start collapsed (matching the Flet tree).

        Args:
            path: The folder's path relative to the root.

        Returns:
            ``True`` if the folder is expanded.
        """
        return path in self._expanded

    # ------------------------------------------------------------------
    #  Private: flattening
    # ------------------------------------------------------------------

    def _flatten(self) -> None:
        """Rebuild all rows from the stored root and collapse state."""
        rows: list[Item] = []
        keys: list[str] = []
        if self._root is not None:
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

        Args:
            directory: The directory to read.
            depth: Nesting depth used for indentation.
            parent_path: Accumulated path relative to the root.
            rows: Row accumulator.
            keys: Identity-key accumulator.
        """
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except (OSError, PermissionError):
            return

        for entry in entries:
            if self._is_hidden(entry):
                continue
            path = f"{parent_path}/{entry.name}" if parent_path else entry.name
            if entry.is_dir():
                rows.append(self._folder_row(path, entry.name, depth))
                keys.append(f"folder:{path}")
                if self.is_folder_expanded(path):
                    self._walk(entry, depth + 1, path, rows, keys)
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

    @staticmethod
    def _is_hidden(entry: Path) -> bool:
        """Return whether an entry is filtered out of the tree.

        Ports the Flet rule: skip names beginning with ``"."`` (except
        ``".gitignore"``) and the ``__pycache__`` directory.

        Args:
            entry: The directory entry to test.

        Returns:
            ``True`` when the entry should be hidden.
        """
        if entry.name in _SKIPPED_NAMES:
            return True
        return entry.name.startswith(".") and entry.name != ".gitignore"
