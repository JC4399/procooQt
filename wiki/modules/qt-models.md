# qt.models — QAbstractListModel layer for QML views

Sources: `src/qt/models/base.py`, `src/qt/models/chat_tab_model.py`,
`src/qt/models/session_menu_model.py`, `src/qt/models/chat_list_model.py`,
`src/qt/models/skill_tree_model.py`, `src/qt/models/tool_mode_model.py`,
`src/qt/models/file_tree_model.py`, `src/qt/models/automation_list_model.py`,
`src/qt/models/notification_list_model.py`

## Purpose

A thin, reusable `QAbstractListModel` base over role-keyed dictionaries, plus
concrete models that drive the QML `ListView`s. Concrete models declare
their roles as an `IntEnum` in [qt-qt-roles](qt-qt-roles.md) and store each row
as a plain `dict[int, Any]` keyed by role id. This keeps the Python side free of
Qt item classes while still giving QML typed role access, and lets the models
support incremental updates rather than full `beginResetModel` resets on every
stream token.

## Role-keyed dicts

- A row is `Item = dict[int, Any]`; keys are `int(ChatListRole.KIND)` etc.
- `data(index, role)` returns `item.get(role)`.
- `get(row)` returns a **string-keyed** map (`{str(role): value}`) for QML, via
  a `QVariantMap` slot.
- Identity keys (`keys`) are per-row strings (e.g. `f"chat:{id}"`) used by
  `diff_update`/`find_divergence` to locate the first changed row.

## Deliverables

- `ListModel` — base model (`roleNames`, `rowCount`, `data`, mutation, QML
  slots).
- `ChatTabModel` — chat tabs for one panel's `ChatTabBar.qml`.
- `SessionMenuModel` — sessions + trailing `+` for `SessionSelector.qml`.
- `ChatListModel` — rendered chat items for `ChatPanel.qml`.
- `SkillTreeModel` — flattened skill/folder tree with selection state.
- `ToolModeModel` — per-tool permission rows grouped by skill.
- `FileTreeModel` — flattened file/folder tree with fuzzy name search for `EditorPanel.qml`.
- `AutomationListModel` — automation cards for `AutomationPanel.qml`.
- `NotificationListModel` — notification cards for the notification page and history.

> The per-panel `ChatPanelModel` (`src/qt/chat_panel_model.py`) is a plain
> `QObject` view model, not a `ListModel`; see
> [`qt-chat-panel-model`](qt-chat-panel-model.md).

## Steps / Flow

### `diff_update` (incremental alignment)

1. Raise `ValueError` if `keys` and `items` differ in length.
2. `find_divergence(keys)` → first mismatching index, or `-1` when up to date.
3. Return `-1` (no change) if already aligned.
4. `beginRemoveRows` and truncate `_items` / `_keys` from the divergence index.
5. `beginInsertRows` and extend with `items[divergence:]` / `keys[divergence:]`.
6. Return the divergence index.

### `find_divergence`

1. Walk `keys`; return the first index whose stored key is missing or differs.
2. If the stored list is longer than `keys`, return `len(keys)`.
3. Otherwise `-1`.

## Function Reference — `ListModel`

### Model contract

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, roles: dict[int, bytes], parent: Any = None) -> None` | `roles` — role-name map; `parent` — Qt parent | — | init `_items` / `_keys` | — |
| `def roleNames(self) -> dict[int, QByteArray]` (N802) | — | role-id → `QByteArray` name | wrap `self.roles` | — |
| `def rowCount(self, parent: ParentIndex = QModelIndex()) -> int` (N802) | `parent` — index | `0` if valid, else `len(self._items)` | — | — |
| `def data(self, index: ParentIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any` | `index`, `role` | stored value or `None` | bounds check → `get(role)` | — |

### Mutation

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def set_items(self, items: list[Item], keys: list[str] \| None = None) -> None` | `items`; optional `keys` (defaults to `""` per row) | `None` | `beginResetModel` → replace lists → `endResetModel` | Full model reset |
| `def diff_update(self, items: list[Item], keys: list[str]) -> int` | `items`, `keys` | divergence index or `-1` | `find_divergence` → remove suffix → insert suffix | Raises `ValueError`; emits row removed/inserted |
| `def find_divergence(self, keys: list[str]) -> int` | `keys` | first differing index, else `-1` | linear scan | — |
| `def append_item(self, item: Item, key: str = "") -> int` | `item`, `key` | new row index | `beginInsertRows` → append | Emits row inserted |
| `def append_items(self, items: list[Item], keys: list[str] \| None = None) -> None` | `items`; optional `keys` | `None` | one `beginInsertRows` for the whole batch → extend | Emits one rows-inserted batch; no-op when empty |
| `def update_item(self, row: int, values: Item) -> None` | `row`, `values` | `None` | merge → `dataChanged.emit(..., list(values.keys()))` | No-op if out of range; emits `dataChanged` |
| `def clear(self) -> None` | — | `None` | `set_items([])` | Full reset |

### Slots (QML access)

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `@Slot(int, result="QVariantMap")`<br>`def get(self, row: int) -> dict[str, Any]` | `row` | string-keyed row or `{}` | bounds check → stringify role keys | — |
| `@Slot(result=int)`<br>`def count(self) -> int` | — | `len(self._items)` | — | — |

### Types

| Name | Definition |
|---|---|
| `ParentIndex` | `QModelIndex \| QPersistentModelIndex` |
| `Item` | `dict[int, Any]` |

## Concrete models

### `ChatTabModel`

Chat tabs for one panel. Rows are built from enriched chat summaries already
filtered to the panel's chats and ordered. Summaries must be pre-enriched with
`title` and `status` by the controller.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `ChatTabRole` |
| `def set_chats(self, chats: list[dict[str, Any]], active_id: str \| None, states: dict[str, ChatState]) -> None` | summaries, active id, per-chat states | `None` | build rows+keys → `set_items`; full reset |
| `def update_chat(self, chat_id: str, status: str, blinking: bool) -> None` | chat id, `ChatStatus`, blink flag | `None` | find row by chat id → `update_item`; role-scoped `dataChanged`, no reset |

### `SessionMenuModel`

Session rows plus an always-present trailing `+` row (role `IS_ADD`) for the
title-bar selector. The `+` row stays visible even when `Default` is the only
session.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `SessionMenuRole` |
| `def set_sessions(self, names: list[str], active_name: str \| None) -> None` | session names, active name | `None` | one row per session + a trailing `+` row → `set_items` |

### `ChatListModel`

Incremental list of chat items for one chat.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `ChatRole` |
| `def find_pending_result(self, tool_call_id: str) -> int` | tool-call id | row index or `-1` | scan rows where `IS_PENDING` and `TOOL_CALL_ID` matches |
| `def replace_item(self, row: int, item: Item, key: str) -> None` | `row`, new `item`, new `key` | `None` | replace row + key, emit `dataChanged` for `item.keys()`; no-op out of range |

### `SkillTreeModel`

Flattens the nested `{folders, skills}` tree from `SkillManager.get_skill_tree`
into depth-tagged rows. Folder collapse and primary/secondary selections are
owned by the model and survive search filtering.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `SkillRole`; init tree/search/collapsed/primary/secondary |
| `def rebuild(self, tree: dict, search: str = "") -> None` | tree, search term | `None` | drop stale selections → `_flatten` |
| `def set_folder_expanded(self, path: str, expanded: bool) -> None` | folder path, flag | `None` | update `_collapsed` → `_flatten` |
| `def is_folder_expanded(self, path: str) -> bool` | folder path | `True` if a search is active or not collapsed | — |
| `def apply_selection(self, primary: set[str], secondary: set[str]) -> None` | path sets | `None` | intersect with valid paths → `_apply_selection_roles` |
| `def set_selection(self, path: str, kind: str, checked: bool) -> None` | path, `"primary"`/`"secondary"`, checked | `None` | mutate set → `_apply_selection_roles` |
| `def collect_selected_primary(self) -> list[str]` | — | sorted primary paths | — |
| `def collect_selected_secondary(self) -> list[str]` | — | sorted secondary paths | — |
| `def selected_union(self) -> set[str]` | — | union of primary + secondary | — |
| `_flatten()` | — | `None` | rebuild rows → `set_items` |
| `_flatten_node(node, depth, parent_path, rows, keys)` | node etc. | `None` | recurse folders (sorted), then skills; search hides empty folders |
| `_folder_row(...)` / `_skill_row(skill, depth)` | row data | `Item` | build role dict; folder gets `SKILL_COUNT`/`SELECTED_COUNT` |
| `_apply_selection_roles()` | — | `None` | `update_item` per row (folders → `SELECTED_COUNT`, skills → `PRIMARY`/`SECONDARY`) |
| `_skill_matches(skill)` | `SkillInfo` | `bool` | case-insensitive name/description match |
| `_count_skills(tree)` / `_count_selected(tree)` | subtree | `int` | recursive counts |
| `_collect_skill_paths(tree)` (`@staticmethod`) | subtree | set of paths | recursive collect |

### `ToolModeModel`

One row per tool, grouped by parent skill. `IS_GROUP_START` is set on the first
tool of each skill so a QML delegate can render the group header inline.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `ToolRole` |
| `def rebuild(self, tools: list[ToolInfo], selected: set[str], modes: dict[str, str], display_names: dict[str, str]) -> None` | all tools, selected skill paths, mode map, display names | `None` | group by skill → sorted → build rows; full reset |
| `def set_mode(self, tool_name: str, mode: str) -> None` | tool name, new mode | `None` | find row by `TOOL_NAME` → `update_item` |
| `_tool_row(tool, display_name, modes, *, is_group_start)` (`@staticmethod`) | tool etc. | `Item` | mode defaults to `"ask"`; `SKILL_SELECTED = True` |

### `FileTreeModel`

Walks the skills root and flattens visible entries into depth-tagged rows.
Folder-first ordering; folder collapse starts collapsed. An optional fuzzy
search term (reusing `fuzzy_match`) filters rows by entry name: a folder whose
name matches keeps its entire subtree, otherwise only the matching descendants
are shown, and all folders render expanded while a term is active.
`FileRole.ICON` carries a short extension label (`"py"`, `"md"`, …) or the
folder marker `"dir"`.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `FileRole`; init `_root`/`_search`/`_expanded` |
| `def rebuild(self, root: Path \| str, search: str = "") -> None` | root path; search term | `None` | store both → `_flatten` |
| `def set_search(self, search: str) -> None` | search term | `None` | store term → `_flatten` |
| `def set_folder_expanded(self, path: str, expanded: bool) -> None` | folder path, flag | `None` | update `_expanded` → `_flatten` |
| `def is_folder_expanded(self, path: str) -> bool` | folder path | `True` if expanded or search active | — |
| `_flatten()` | — | `None` | search → `_walk_search`, else `_walk` → `set_items` |
| `_walk(directory, depth, parent_path, rows, keys)` | dir etc. | `None` | no-search flatten: sorted entries → recurse expanded folders |
| `_walk_search(directory, depth, parent_path, rows, keys) -> bool` | dir etc. | subtree has a match | fuzzy filter: matching folder keeps whole subtree; childless-of-match folders dropped |
| `_walk_all(directory, depth, parent_path, rows, keys)` | dir etc. | `None` | dump every descendant ignoring `_expanded`; used under a matched folder |
| `_matches(name: str) -> bool` | display name | fuzzy pass | delegates to `fuzzy_match(_search, name)` |
| `_sorted_entries(directory) -> list[Path]` (`@staticmethod`) | dir | visible-order entries | folders-first sort; `[]` on `OSError`/`PermissionError` |
| `_join(parent_path: str, name: str) -> str` (`@staticmethod`) | parent path; child name | child's root-relative path | — |
| `_folder_row(path, name, depth)` / `_file_row(path, name, depth)` (`@staticmethod`) | row data | `Item` | file icon via `_EXT_TO_LABEL` |
| `_is_hidden(entry)` (`@staticmethod`) | `Path` | `bool` | skip `__pycache__` and dotfiles except `.gitignore` |

### Module constants (`file_tree_model.py`)

| Name | Value / purpose |
|---|---|
| `FOLDER_ICON` | `"dir"` — directory marker |
| `FILE_ICON` | `"file"` — fallback for unknown extensions |
| `_EXT_TO_LABEL` | extension → short label (`.py` → `"py"`, `.yaml` → `"yaml"`, …) |
| `_SKIPPED_NAMES` | `{"__pycache__"}` |

### `AutomationListModel`

Automation cards, filtered by a fuzzy subsequence match over name, description,
event, and schedule. `SCHEDULE_TEXT` is the cron expression, or
`"Event driven (<event>)"` for event automations. `RUNNING` marks an automation
with an in-flight manual run (drives the card's spinner and disabled button).
`WINDOW_TEXT` renders the optional `start_date`/`end_date` frontmatter window as
`YYYY-MM-DD → YYYY-MM-DD · pending|active|expired` (`""` when no dates set).

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `AutomationRole` |
| `def set_automations(self, automations: list[AutomationInfo], search: str = "", running: set[str] \| None = None) -> None` | automations; fuzzy filter; running paths | `None` | filter → build rows → `set_items`; full reset |
| `def set_running(self, path: str, running: bool) -> None` | path; running | `None` | locate row by key → `update_item` (`RUNNING`); no reset |
| `fuzzy_match(query, text) module fn -> bool` | query; text | subsequence match | case-insensitive ordered scan |
| `_row(info, running)` (`@staticmethod`) | automation; running paths | role dict | flattens one card row incl. `WINDOW_TEXT` |
| `_window_text(info)` / `_window_status(info)` (`@staticmethod`) | automation | display text / status word | range + `pending`/`active`/`expired` via `parse_iso_date` |

### `NotificationListModel`

Notification cards for the notification page (`set_notifications`, full reset) and
history paging (`append_notifications`).

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `NotificationRole` |
| `def set_notifications(self, items: list[NotificationItem]) -> None` | items | `None` | build rows+keys → `set_items` |
| `def append_notifications(self, items: list[NotificationItem]) -> None` | items | `None` | `append_items` (one insert batch) |
| `row(item) static -> Item` | notification | role dict | id/kind/task/message/log/timestamp/read/path |

## See also

- [qt-qt-roles](qt-qt-roles.md) — the role enums these models expose.
- [qt-markdown](qt-markdown.md) / [qt-yaml-highlight](qt-yaml-highlight.md) —
  produce the `ChatRole.BODY_HTML` values stored in rows.
- [qt-error-handler](qt-error-handler.md) — controllers surface failures via
  `toast_requested` when model rebuilds fail.
