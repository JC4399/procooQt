"""Model role definitions exposed to QML.

Each ``ListModel`` advertises its roles to QML via ``roleNames``. Roles are declared
here as ``IntEnum`` members so Python and QML agree on a single set of names.
"""

from __future__ import annotations

from enum import IntEnum


class ChatTabRole(IntEnum):
    """Roles for :class:`~src.qt.models.chat_tab_model.ChatTabModel`."""

    CHAT_ID = 1
    TITLE = 2
    STATUS = 3
    IS_ACTIVE = 4
    IS_BLINKING = 5
    MESSAGE_COUNT = 6


class SessionMenuRole(IntEnum):
    """Roles for :class:`~src.qt.models.session_menu_model.SessionMenuModel`."""

    NAME = 1
    IS_ADD = 2
    IS_ACTIVE = 3


class ChatRole(IntEnum):
    """Roles for :class:`~src.qt.models.chat_list_model.ChatListModel`."""

    KIND = 1
    TITLE = 2
    BODY_HTML = 3
    TOKEN_TEXT = 4
    COLLAPSED = 5
    IS_PENDING = 6
    MODE = 7
    TOOL_NAME = 8
    TOOL_CALL_ID = 9
    SECTIONS = 10
    IS_DELTA = 11


class SkillRole(IntEnum):
    """Roles for :class:`~src.qt.models.skill_tree_model.SkillTreeModel`."""

    PATH = 1
    NAME = 2
    DESCRIPTION = 3
    DEPTH = 4
    IS_FOLDER = 5
    PRIMARY = 6
    SECONDARY = 7
    HAS_TOOLS = 8
    EXPANDED = 9
    SKILL_COUNT = 10
    SELECTED_COUNT = 11


class ToolRole(IntEnum):
    """Roles for :class:`~src.qt.models.tool_mode_model.ToolModeModel`."""

    TOOL_NAME = 1
    SKILL_PATH = 2
    DESCRIPTION = 3
    MODE = 4
    SKILL_DISPLAY_NAME = 5
    IS_GROUP_START = 6
    SKILL_SELECTED = 7


class FileRole(IntEnum):
    """Roles for :class:`~src.qt.models.file_tree_model.FileTreeModel`."""

    PATH = 1
    NAME = 2
    DEPTH = 3
    IS_FOLDER = 4
    ICON = 5


def role_names(enum_cls: type[IntEnum]) -> dict[int, bytes]:
    """Build the ``roleNames`` mapping for a role enum.

    Args:
        enum_cls: An ``IntEnum`` whose member names are the QML role names.

    Returns:
        A mapping of role id to the UTF-8 role name, suitable for
        ``QAbstractListModel.roleNames``.
    """
    return {int(member): member.name.lower().encode("utf-8") for member in enum_cls}
