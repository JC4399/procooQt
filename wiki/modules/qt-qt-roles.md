# qt.qt_roles — model roles exposed to QML

Source: `src/qt/qt_roles.py`

## Purpose

Every `ListModel` advertises its roles to QML through `roleNames`. Each concrete
model declares those roles as an `IntEnum` here so the Python side and the QML
delegates agree on one set of role ids and names. `role_names()` converts an
enum into the `{role id: bytes}` mapping Qt expects.

## Deliverables

- `ChatTabRole`, `SessionMenuRole`, `ChatRole`, `SkillRole`, `ToolRole`,
  `FileRole`, `AutomationRole`, `NotificationRole` — role enums.
- `role_names(enum_cls) -> dict[int, bytes]` — role-name builder.

## How roles are used

- Rows are stored as `dict[int, Any]` keyed by `int(Role.MEMBER)`; see
  [qt-models](qt-models.md).
- `roleNames()` lower-cases each enum member name and UTF-8 encodes it, so
  `ChatTabRole.CHAT_ID` becomes the QML role `chat_id`.
- QML delegates read the lower-cased role name directly, e.g.
  `model.body_html`, `model.is_session`.

## Role reference

### `ChatTabRole` — `ChatTabModel`

| Member | Value | Meaning |
|---|---|---|
| `CHAT_ID` | 1 | Chat id |
| `TITLE` | 2 | Derived chat title |
| `STATUS` | 3 | Chat status string |
| `IS_ACTIVE` | 4 | `True` for the panel's active chat |
| `IS_BLINKING` | 5 | `True` while the chat is busy |
| `MESSAGE_COUNT` | 6 | Message count |

### `SessionMenuRole` — `SessionMenuModel`

| Member | Value | Meaning |
|---|---|---|
| `NAME` | 1 | Session name (`+` for the add row) |
| `IS_ADD` | 2 | `True` for the trailing add row |
| `IS_ACTIVE` | 3 | `True` for the active session |

### `ChatRole` — `ChatListModel`

| Member | Value | Meaning |
|---|---|---|
| `KIND` | 1 | Card kind (user/thinking/response/tool/result) |
| `TITLE` | 2 | Card header label |
| `BODY_HTML` | 3 | Inline-styled rendered HTML body |
| `TOKEN_TEXT` | 4 | Token-count label |
| `COLLAPSED` | 5 | Initial body collapse state (bound to `bodyCollapsed` for context banners) |
| `IS_PENDING` | 6 | `True` for a streaming placeholder card |
| `MODE` | 7 | Tool-approval mode (allow/ask/block) |
| `TOOL_NAME` | 8 | Tool name |
| `TOOL_CALL_ID` | 9 | Tool-call id (links call to result) |
| `SECTIONS` | 10 | Structured body sections |
| `IS_DELTA` | 11 | `True` for an incremental append |

### `SkillRole` — `SkillTreeModel`

| Member | Value | Meaning |
|---|---|---|
| `PATH` | 1 | Relative skill/folder path |
| `NAME` | 2 | Display name |
| `DESCRIPTION` | 3 | Skill description |
| `DEPTH` | 4 | Nesting depth for indentation |
| `IS_FOLDER` | 5 | `True` for a folder row |
| `PRIMARY` | 6 | Selected as primary |
| `SECONDARY` | 7 | Selected as secondary |
| `HAS_TOOLS` | 8 | Skill declares tools |
| `EXPANDED` | 9 | Folder expansion state |
| `SKILL_COUNT` | 10 | Total skills in a folder subtree |
| `SELECTED_COUNT` | 11 | Selected skills in a folder subtree |

### `ToolRole` — `ToolModeModel`

| Member | Value | Meaning |
|---|---|---|
| `TOOL_NAME` | 1 | Tool name |
| `SKILL_PATH` | 2 | Owning skill path |
| `DESCRIPTION` | 3 | Tool description |
| `MODE` | 4 | Permission mode (allow/ask/block) |
| `SKILL_DISPLAY_NAME` | 5 | Parent skill's display name |
| `IS_GROUP_START` | 6 | `True` on the first tool of a skill group |
| `SKILL_SELECTED` | 7 | Parent skill currently selected |

### `FileRole` — `FileTreeModel`

| Member | Value | Meaning |
|---|---|---|
| `PATH` | 1 | Path relative to the capabilities root |
| `NAME` | 2 | Display name |
| `DEPTH` | 3 | Nesting depth for indentation |
| `IS_FOLDER` | 4 | `True` for a directory row |
| `ICON` | 5 | Extension label or `"dir"` marker |

### `AutomationRole` — `AutomationListModel`

| Member | Value | Meaning |
|---|---|---|
| `PATH` | 1 | Automation path relative to the automations root |
| `NAME` | 2 | Display name |
| `DESCRIPTION` | 3 | Description |
| `ACTIVATION` | 4 | `scheduled` / `event` |
| `SCHEDULE_TEXT` | 5 | Cron expression, or `Event driven (<event>)` |
| `ENABLED` | 6 | Enable toggle state |
| `LAST_RUN` | 7 | Last-run timestamp |
| `EVENT` | 8 | Event name (event automations) |
| `RUNNING` | 9 | Whether a manual run is in flight |

### `NotificationRole` — `NotificationListModel`

| Member | Value | Meaning |
|---|---|---|
| `ID` | 1 | Notification id (Confirm/Debug) |
| `KIND` | 2 | `log` / `info` / `error` (card colour) |
| `TASK` | 3 | Source automation name |
| `MESSAGE` | 4 | Result message |
| `LOG` | 5 | Detailed run log |
| `TIMESTAMP` | 6 | Completion time |
| `READ` | 7 | Read flag |
| `PATH` | 8 | Source automation path (Debug target) |

## Function Reference

### `role_names`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def role_names(enum_cls: type[IntEnum]) -> dict[int, bytes]` | `enum_cls` — role `IntEnum` | `{int(member): member.name.lower().encode("utf-8")}` | iterate members → lower-case → UTF-8 encode | None |

## See also

- [qt-models](qt-models.md) — the `ListModel` base and concrete models that
  consume these roles.
