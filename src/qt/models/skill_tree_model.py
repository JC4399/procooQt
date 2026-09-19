"""``SkillTreeModel`` — flattened skill/folder tree for ``SkillPanel.qml``.

The nested ``{folders, skills}`` tree returned by ``SkillManager.get_skill_tree`` is
flattened into rows (folders and skills) so a QML delegate can render the whole tree in
one list. Folder collapse state and the primary/secondary selections are owned by the
model and survive search filtering; a selection made while a skill is hidden by the
search term is preserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.base import Item, ListModel
from ..qt_roles import SkillRole, role_names

if TYPE_CHECKING:
    from ...skill.models import SkillInfo

EMPTY_TREE: dict = {"folders": {}, "skills": []}


class SkillTreeModel(ListModel):
    """Flattened (depth-tagged) skill tree model with search and selection state.

    Attributes:
        roles: Skill role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the skill tree model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(SkillRole), parent)
        self._tree: dict = dict(EMPTY_TREE)
        self._search = ""
        self._collapsed: set[str] = set()
        self._primary: set[str] = set()
        self._secondary: set[str] = set()
        self._folder_nodes: dict[str, dict] = {}

    # ------------------------------------------------------------------
    #  Public: structure
    # ------------------------------------------------------------------

    def rebuild(self, tree: dict, search: str = "") -> None:
        """Replace the tree and search term, then re-flatten into rows.

        Selections for skills that no longer exist are dropped.

        Args:
            tree: Nested skill tree with ``folders`` and ``skills`` keys.
            search: Optional case-insensitive filter matched against skill name
                and description. Folders expand while a search term is active.
        """
        self._tree = tree or dict(EMPTY_TREE)
        self._search = (search or "").strip()
        valid = self._collect_skill_paths(self._tree)
        self._primary &= valid
        self._secondary &= valid
        self._flatten()

    def set_folder_expanded(self, path: str, expanded: bool) -> None:
        """Record a folder's collapse state and re-flatten the rows.

        Args:
            path: The folder's relative path.
            expanded: ``True`` to show the folder's children.
        """
        if expanded:
            self._collapsed.discard(path)
        else:
            self._collapsed.add(path)
        self._flatten()

    def is_folder_expanded(self, path: str) -> bool:
        """Return whether a folder's children are currently shown.

        Args:
            path: The folder's relative path.

        Returns:
            ``True`` if the folder is expanded (or a search is active).
        """
        return bool(self._search) or path not in self._collapsed

    # ------------------------------------------------------------------
    #  Public: selection
    # ------------------------------------------------------------------

    def apply_selection(self, primary: set[str], secondary: set[str]) -> None:
        """Set the primary/secondary selections and refresh the affected roles.

        Args:
            primary: Primary skill paths.
            secondary: Secondary skill paths.
        """
        valid = self._collect_skill_paths(self._tree)
        self._primary = set(primary) & valid
        self._secondary = set(secondary) & valid
        self._apply_selection_roles()

    def set_selection(self, path: str, kind: str, checked: bool) -> None:
        """Set one skill's primary or secondary selection.

        Args:
            path: The skill's relative path.
            kind: Either ``"primary"`` or ``"secondary"``.
            checked: The new checkbox state.
        """
        target = self._primary if kind == "primary" else self._secondary
        if checked:
            target.add(path)
        else:
            target.discard(path)
        self._apply_selection_roles()

    def collect_selected_primary(self) -> list[str]:
        """Return the selected primary skill paths in display order.

        Returns:
            Sorted list of primary skill paths.
        """
        return sorted(self._primary)

    def collect_selected_secondary(self) -> list[str]:
        """Return the selected secondary skill paths in display order.

        Returns:
            Sorted list of secondary skill paths.
        """
        return sorted(self._secondary)

    def selected_union(self) -> set[str]:
        """Return the union of selected primary and secondary skill paths.

        Returns:
            Set of skill paths selected in either column.
        """
        return self._primary | self._secondary

    # ------------------------------------------------------------------
    #  Private: flattening
    # ------------------------------------------------------------------

    def _flatten(self) -> None:
        """Rebuild all rows from the stored tree, search, and selections."""
        rows: list[Item] = []
        keys: list[str] = []
        self._folder_nodes = {}
        self._flatten_node(self._tree, 0, "", rows, keys)
        self.set_items(rows, keys)

    def _flatten_node(
        self,
        node: dict,
        depth: int,
        parent_path: str,
        rows: list[Item],
        keys: list[str],
    ) -> None:
        """Append the rows for one tree node, recursing into child folders.

        Args:
            node: The tree node to flatten.
            depth: Nesting depth used for indentation.
            parent_path: Accumulated parent folder path.
            rows: Row accumulator.
            keys: Identity-key accumulator.
        """
        for folder_name in sorted(node.get("folders", {})):
            folder_tree = node["folders"][folder_name]
            folder_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
            child_rows: list[Item] = []
            child_keys: list[str] = []
            self._flatten_node(folder_tree, depth + 1, folder_path, child_rows, child_keys)
            if self._search and not child_rows:
                continue
            self._folder_nodes[folder_path] = folder_tree
            expanded = self.is_folder_expanded(folder_path)
            rows.append(self._folder_row(folder_path, folder_name, depth, expanded, folder_tree))
            keys.append(f"folder:{folder_path}")
            if expanded:
                rows.extend(child_rows)
                keys.extend(child_keys)

        for skill in sorted(node.get("skills", []), key=lambda s: s.path):
            if not self._skill_matches(skill):
                continue
            rows.append(self._skill_row(skill, depth))
            keys.append(f"skill:{skill.path}")

    def _folder_row(
        self,
        path: str,
        name: str,
        depth: int,
        expanded: bool,
        folder_tree: dict,
    ) -> Item:
        """Build a folder header row.

        Args:
            path: Folder relative path.
            name: Folder display name.
            depth: Nesting depth.
            expanded: Whether the folder's children are shown.
            folder_tree: The folder's subtree (used for count badges).

        Returns:
            A role-keyed folder row.
        """
        return {
            int(SkillRole.PATH): path,
            int(SkillRole.NAME): name,
            int(SkillRole.DESCRIPTION): "",
            int(SkillRole.DEPTH): depth,
            int(SkillRole.IS_FOLDER): True,
            int(SkillRole.PRIMARY): False,
            int(SkillRole.SECONDARY): False,
            int(SkillRole.HAS_TOOLS): False,
            int(SkillRole.EXPANDED): expanded,
            int(SkillRole.SKILL_COUNT): self._count_skills(folder_tree),
            int(SkillRole.SELECTED_COUNT): self._count_selected(folder_tree),
        }

    def _skill_row(self, skill: SkillInfo, depth: int) -> Item:
        """Build a skill row.

        Args:
            skill: The discovered skill.
            depth: Nesting depth.

        Returns:
            A role-keyed skill row.
        """
        return {
            int(SkillRole.PATH): skill.path,
            int(SkillRole.NAME): skill.name,
            int(SkillRole.DESCRIPTION): skill.description,
            int(SkillRole.DEPTH): depth,
            int(SkillRole.IS_FOLDER): False,
            int(SkillRole.PRIMARY): skill.path in self._primary,
            int(SkillRole.SECONDARY): skill.path in self._secondary,
            int(SkillRole.HAS_TOOLS): skill.has_tools,
            int(SkillRole.EXPANDED): False,
            int(SkillRole.SKILL_COUNT): 0,
            int(SkillRole.SELECTED_COUNT): 0,
        }

    # ------------------------------------------------------------------
    #  Private: selection role refresh
    # ------------------------------------------------------------------

    def _apply_selection_roles(self) -> None:
        """Push current selections into the existing rows without a reset."""
        for row in range(self.count()):
            item = self._items[row]
            path = item.get(int(SkillRole.PATH), "")
            if item.get(int(SkillRole.IS_FOLDER)):
                folder_tree = self._folder_nodes.get(path, {})
                values = {int(SkillRole.SELECTED_COUNT): self._count_selected(folder_tree)}
            else:
                values = {
                    int(SkillRole.PRIMARY): path in self._primary,
                    int(SkillRole.SECONDARY): path in self._secondary,
                }
            self.update_item(row, values)

    # ------------------------------------------------------------------
    #  Private: tree helpers
    # ------------------------------------------------------------------

    def _skill_matches(self, skill: SkillInfo) -> bool:
        """Return whether a skill passes the active search filter.

        Args:
            skill: The skill to test.

        Returns:
            ``True`` when there is no search term or the term appears in the
            skill's name or description (case-insensitive).
        """
        if not self._search:
            return True
        term = self._search.lower()
        return term in skill.name.lower() or term in (skill.description or "").lower()

    @staticmethod
    def _count_skills(tree: dict) -> int:
        """Count all skills in a subtree, including nested folders.

        Args:
            tree: A skill tree node.

        Returns:
            Total skill count for the subtree.
        """
        count = len(tree.get("skills", []))
        for folder_tree in tree.get("folders", {}).values():
            count += SkillTreeModel._count_skills(folder_tree)
        return count

    def _count_selected(self, tree: dict) -> int:
        """Count selected skills in a subtree, including nested folders.

        Args:
            tree: A skill tree node.

        Returns:
            Number of skills selected as primary or secondary.
        """
        selected = self._primary | self._secondary
        count = sum(1 for s in tree.get("skills", []) if s.path in selected)
        for folder_tree in tree.get("folders", {}).values():
            count += self._count_selected(folder_tree)
        return count

    @staticmethod
    def _collect_skill_paths(tree: dict) -> set[str]:
        """Collect every ``skill.path`` in a subtree.

        Args:
            tree: A skill tree node.

        Returns:
            Set of skill paths under the node.
        """
        paths = {s.path for s in tree.get("skills", [])}
        for folder_tree in tree.get("folders", {}).values():
            paths |= SkillTreeModel._collect_skill_paths(folder_tree)
        return paths
