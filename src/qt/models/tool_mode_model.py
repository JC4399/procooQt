"""``ToolModeModel`` — per-tool permission mode (allow/ask/block) rows.

Tools are grouped by their parent skill path. The controller provides the flattened
tool list, the set of selected skills, and the current mode map; the model emits one row
per tool with ``IS_GROUP_START`` set on the first tool of each skill so a QML delegate
can render the group header inline while iterating a single ``Repeater``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.base import Item, ListModel
from ..qt_roles import ToolRole, role_names

if TYPE_CHECKING:
    from ...skill.models import ToolInfo


class ToolModeModel(ListModel):
    """List model of tools and their permission modes, grouped by skill.

    Attributes:
        roles: Tool role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the tool mode model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(ToolRole), parent)

    # ------------------------------------------------------------------
    #  Public: build
    # ------------------------------------------------------------------

    def rebuild(
        self,
        tools: list[ToolInfo],
        selected: set[str],
        modes: dict[str, str],
        display_names: dict[str, str],
    ) -> None:
        """Rebuild rows for the tools of selected skills.

        Args:
            tools: Every discovered tool.
            selected: Skill paths currently selected as activated.
            modes: Mapping of tool name to mode (``"allow"``/``"ask"``/``"block"``).
            display_names: Mapping of skill path to display name for group headers.
        """
        by_skill: dict[str, list[ToolInfo]] = {}
        for tool in tools:
            by_skill.setdefault(tool.skill_path, []).append(tool)

        rows: list[Item] = []
        keys: list[str] = []
        for skill_path in sorted(by_skill):
            if skill_path not in selected:
                continue
            skill_tools = sorted(by_skill[skill_path], key=lambda t: t.name)
            display = display_names.get(skill_path, skill_path)
            for index, tool in enumerate(skill_tools):
                rows.append(self._tool_row(tool, display, modes, is_group_start=index == 0))
                keys.append(f"tool:{skill_path}:{tool.name}")
        self.set_items(rows, keys)

    def set_mode(self, tool_name: str, mode: str) -> None:
        """Update one tool's mode in place.

        Args:
            tool_name: The tool whose mode changed.
            mode: The new mode (``"allow"``/``"ask"``/``"block"``).
        """
        for row in range(self.count()):
            if self._items[row].get(int(ToolRole.TOOL_NAME)) == tool_name:
                self.update_item(row, {int(ToolRole.MODE): mode})
                return

    # ------------------------------------------------------------------
    #  Private: row builder
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_row(
        tool: ToolInfo,
        display_name: str,
        modes: dict[str, str],
        *,
        is_group_start: bool,
    ) -> Item:
        """Build one tool row.

        Args:
            tool: The discovered tool.
            display_name: Display name of the parent skill.
            modes: Mapping of tool name to mode.
            is_group_start: Whether this is the first tool of its skill group.

        Returns:
            A role-keyed tool row.
        """
        return {
            int(ToolRole.TOOL_NAME): tool.name,
            int(ToolRole.SKILL_PATH): tool.skill_path,
            int(ToolRole.DESCRIPTION): tool.description,
            int(ToolRole.MODE): modes.get(tool.name, "ask"),
            int(ToolRole.SKILL_DISPLAY_NAME): display_name,
            int(ToolRole.IS_GROUP_START): is_group_start,
            int(ToolRole.SKILL_SELECTED): True,
        }
