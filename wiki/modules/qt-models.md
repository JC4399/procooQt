# qt.models — QAbstractListModel layer for QML views

Sources: `src/qt/models/base.py`, `src/qt/models/session_list_model.py`,
`src/qt/models/chat_list_model.py`, `src/qt/models/skill_tree_model.py`,
`src/qt/models/tool_mode_model.py`, `src/qt/models/file_tree_model.py`

## Purpose

A thin, reusable `QAbstractListModel` base over role-keyed dictionaries, plus
five concrete models that drive the QML `ListView`s. Concrete models declare
their roles as an `IntEnum` in [qt-qt-roles](qt-qt-roles.md) and store each row
as a plain `dict[int, Any]` keyed by role id. This keeps the Python side free of
Qt item classes while still giving QML typed role access, and lets the models
support incremental updates rather than full `beginResetModel` resets on every
stream token.

## Role-keyed dicts

- A row is `Item = dict[int, Any]`; keys are `int(SessionRole.PRIMARY)` etc.
- `data(index, role)` returns `item.get(role)`.
- `get(row)` returns a **string-keyed** map (`{str(role): value}`) for QML, via
  a `QVariantMap` slot.
- Identity keys (`keys`) are per-row strings (e.g. `f"session:{id}"`) used by
  `diff_update`/`find_divergence` to locate the first changed row.

## Deliverables

- `ListModel` — base model (`roleNames`, `rowCount`, `data`, mutation, QML
  slots).
- `SessionListModel` — folders + session tiles for `SessionPanel.qml`.
- `ChatListModel` — rendered chat items for `ChatPanel.qml`.
- `SkillTreeModel` — flattened skill/folder tree with selection state.
- `ToolModeModel` — per-tool permission rows grouped by skill.
- `FileTreeModel` — flattened file/folder tree for `EditorPanel.qml`.

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

### `SessionListModel`

Flattens folders and (expanded) sessions into one list. Folder headers are
always emitted; session rows follow only while the folder is expanded. Unfiled
sessions render after the folders with no synthetic header. Summaries must be
pre-enriched with `title` and `status` by the controller.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `SessionRole`; init `_expanded` |
| `def set_folder_expansion(self, name: str, expanded: bool) -> None` | folder `name`, `expanded` | `None` | stores expansion, no re-flatten |
| `def is_expanded(self, name: str) -> bool` | `name` | expanded flag (default `False`) | — |
| `def set_sessions(self, sessions: list[dict[str, Any]], folders: list[str], active_id: str \| None, states: dict[str, SessionState]) -> None` | summaries, folder order, active id, per-session states | `None` | build rows+keys → `set_items`; full reset |
| `_append_folder(rows, keys, folder, session_count)` | accumulators, folder, count | `None` | appends header; `MESSAGE_COUNT` = session count; key `folder:{name}` |
| `_append_session(rows, keys, session, active_id, states)` | accumulators, session, active id, states | `None` | appends tile; `IS_BLINKING = is_busy and not pending_tool_info`; key `session:{id}` |

### `ChatListModel`

Incremental list of chat items for one session.

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
Folder-first ordering; folder collapse starts collapsed. `FileRole.ICON` carries
a short extension label (`"py"`, `"md"`, …) or the folder marker `"dir"`.

| Signature | Inputs | Output | Flow / Side effects |
|---|---|---|---|
| `def __init__(self, parent: Any = None) -> None` | `parent` | — | roles = `FileRole`; init `_root`/`_expanded` |
| `def rebuild(self, root: Path \| str) -> None` | root path | `None` | store root → `_flatten` |
| `def set_folder_expanded(self, path: str, expanded: bool) -> None` | folder path, flag | `None` | update `_expanded` → `_flatten` |
| `def is_folder_expanded(self, path: str) -> bool` | folder path | `True` if expanded | — |
| `_flatten()` | — | `None` | `_walk` root → `set_items` |
| `_walk(directory, depth, parent_path, rows, keys)` | dir etc. | `None` | sorted entries → recurse expanded folders; swallows `OSError`/`PermissionError` |
| `_folder_row(path, name, depth)` / `_file_row(path, name, depth)` (`@staticmethod`) | row data | `Item` | file icon via `_EXT_TO_LABEL` |
| `_is_hidden(entry)` (`@staticmethod`) | `Path` | `bool` | skip `__pycache__` and dotfiles except `.gitignore` |

### Module constants (`file_tree_model.py`)

| Name | Value / purpose |
|---|---|
| `FOLDER_ICON` | `"dir"` — directory marker |
| `FILE_ICON` | `"file"` — fallback for unknown extensions |
| `_EXT_TO_LABEL` | extension → short label (`.py` → `"py"`, `.yaml` → `"yaml"`, …) |
| `_SKIPPED_NAMES` | `{"__pycache__"}` |

## See also

- [qt-qt-roles](qt-qt-roles.md) — the role enums these models expose.
- [qt-markdown](qt-markdown.md) / [qt-yaml-highlight](qt-yaml-highlight.md) —
  produce the `ChatRole.BODY_HTML` values stored in rows.
- [qt-error-handler](qt-error-handler.md) — controllers surface failures via
  `toast_requested` when model rebuilds fail.
