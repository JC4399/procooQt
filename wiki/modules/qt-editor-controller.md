# qt.editor_controller — code editor & file tree

Source: `src/qt/editor_controller.py`

## Purpose

Drives the separate code editor window (`src/qml/windows/EditorWindow.qml`, which
hosts `EditorPanel.qml`): a read-only code editor backed by a QML `TextArea`, a
collapsible file tree rooted at the **capabilities directory** (left of the code
pane) with a fuzzy search field above it, and Edit/Save/Cancel/Reload actions. It
also attaches a `QSyntaxHighlighter` to the `TextArea`'s text document.

While the window is showing, the skill watcher keeps the tree and the open file
in sync with disk. A deleted or externally modified open file raises
`file_conflict`; QML prompts (keep buffer vs. take disk state) and resolves it
through the conflict slots. File reads and writes are offloaded with
`asyncio.to_thread` so the qasync loop never blocks. QML stays view-only.

## Deliverables

- `FileTreeModel` (`editor.file_model`) — flattened file/folder rows with a
  fuzzy name search (matched folders keep their entire subtree).
- `EditorController` (`QObject`) with signals, `Q_PROPERTY` accessors, and `@Slot`
  handlers for file clicks, folder toggles, edit/save/cancel/reload, the skill
  watcher, window visibility, conflict resolution, and opening an automation.
- Visibility-gated watcher reconciliation (`_refresh_from_watcher`,
  `_reload_open_file_if_changed`) plus the `file_conflict` prompt contract.
- `attachHighlighter` bridge to `src/qt/highlighter.py`.
- `detect_language` + the `_EXT_TO_LANGUAGE` extension map.
- `src/qml/windows/EditorWindow.qml` + `src/qml/panels/EditorPanel.qml` (file tree
  left of the code pane, chat pane right, themed conflict dialog).

## Signals & properties

| Signal | Payload | Emitted when |
|---|---|---|
| `file_tree_changed` | — | File tree rebuilt or a folder toggled; notifies `file_model`. |
| `current_file_changed` | `str` | Open/load/save/buffer update; notifies `currentFile`, `currentText`, `language`. |
| `edit_mode_changed` | `bool` | Edit mode toggled; notifies `editing`. |
| `file_conflict` | `str, str` | `(kind, path)` — the open file was deleted (`"deleted"`) or changed on disk (`"modified"`); QML prompts to keep the buffer or take the on-disk state. |
| `toast_requested` | `str, str` | A message + toast level (`TOAST_INFO` / `TOAST_WARNING` / `TOAST_ERROR`). |
| `editor_open_requested` | — | An external action (notification Debug, automation Edit) asked to show the editor window; wired to `windows.show_editor` by [`qt-ui`](qt-ui.md). |

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `file_model` | `QObject` | `file_tree_changed` | Flattened file tree for `EditorPanel.qml`. |
| `currentFile` | `str` | `current_file_changed` | Path of the open file, or `""`. |
| `currentText` | `str` | `current_file_changed` | Last loaded/saved buffer (writable). |
| `editing` | `bool` | `edit_mode_changed` | Whether the buffer is editable. |
| `language` | `str` | `current_file_changed` | Active highlighter language. |

## Steps / Flow

### Build (`build`)

1. Create `FileTreeModel`; initialise `_current_path`, `_current_text`,
   `_language="plain"`, `_is_editing=False`, `_search_text=""`, highlighter/document
   wrappers, `_tasks`.
2. `_refresh_file_tree()` emits `file_tree_changed`.

### Start (`start`)

`_refresh_file_tree()` re-walks `app.capabilities_dir` and emits.

### Watcher reconciliation (visibility-gated)

1. `SkillController.skill_files_changed` is wired to
   `_handle_skill_files_changed` in `ProcooQtUI.__init__` (queued from the watchdog
   thread to the GUI thread).
2. The slot is a no-op while `_active` (editor window showing) is `False`; the
   editor leaves the stale open file alone until it is visible again.
3. `_refresh_from_watcher` `await asyncio.to_thread(_file_model.rebuild, capabilities_dir)`,
   emits `file_tree_changed` (`ListModel.set_items` resets the view), then calls
   `_reload_open_file_if_changed`.
4. `_handle_window_visibility(visible)` updates `_active`; when it turns on it
   re-syncs. A conflict left pending is re-emitted instead, so the dialog reopens.

### Conflict resolution

`_reload_open_file_if_changed` compares the open file with disk:

1. Missing file → `_open_conflict("deleted", path, 0.0)`.
2. `st_mtime == _disk_mtime` → nothing (the known on-disk state).
3. Content equals `_current_text` → record the new mtime, no prompt (covers our
   own saves).
4. Otherwise → `_open_conflict("modified", path, mtime)`.

`_open_conflict` stores `_conflict_kind` / `_conflict_path` / `_conflict_mtime`
and emits `file_conflict`; QML renders the dialog.

- `_handle_conflict_keep`: `"deleted"` → `_save(_current_text)` recreates the file
  from the buffer; `"modified"` → keep the buffer and set `_disk_mtime` to the
  conflicted mtime so it is not re-prompted until the file changes again.
- `_handle_conflict_discard`: `"deleted"` → leave edit mode, clear the buffer and
  emit `current_file_changed("")` (file closed in the editor); `"modified"` →
  leave edit mode and reload the file from disk.

Both clear the pending conflict via `_clear_conflict`.

### Open file (`_handle_file_click` → `_open_file_in_editor` → `_load_file_into_editor`)

1. Folders toggle expansion via `_handle_folder_toggle`; files resolve to an
   absolute path under `app.capabilities_dir`.
2. `_open_file_in_editor` refuses while `editing` (warning toast), else spawns
   `_load_file_into_editor`.
3. `_load_file_into_editor` `await asyncio.to_thread(_read_file)` (content +
   `st_mtime`); on success sets `_current_path` / `_current_text` / `_disk_mtime`,
   `detect_language`, updates the highlighter language, emits
   `current_file_changed`. Read errors toast.

### File tree search (`_handle_search_changed` / `_handle_clear_search`)

The search field at the top of the file tree pane (styled like the
[SkillDock](qt-skill-controller.md) search) calls `_handle_search_changed(text)`;
the "×" button clears the field and calls `_handle_clear_search`.

1. The term is stored in `_search_text` (so watcher rebuilds keep the filter —
   `_refresh_file_tree` and `_refresh_from_watcher` pass it to
   `FileTreeModel.rebuild`) and forwarded to `FileTreeModel.set_search`.
2. The model re-flattens with a fuzzy (case-insensitive subsequence, reusing
   `fuzzy_match`) filter over entry names: a matching file is kept; a folder
   whose name matches keeps its **entire subtree** (expand state ignored); a
   non-matching folder is kept only when a descendant matches, showing just the
   matching chain.
3. While a term is active every folder renders expanded
   (`is_folder_expanded` returns `True`), matching the skill tree's search
   behavior; the stored collapse state resumes when the filter clears.
4. Emits `file_tree_changed`.

### Edit mode / save / cancel / reload

- `_handle_edit` enters edit mode (warning when no file is open).
- `_handle_save(text)` writes the QML buffer to disk off-loop via `_write_file`,
  records the returned mtime in `_disk_mtime`, exits edit mode, toasts success,
  and emits `current_file_changed`.
- `_handle_cancel` leaves edit mode and reloads the file from disk.
- `_handle_reload` leaves edit mode and reloads the file from disk.

### Dirty-state handling (QML)

`EditorPanel.qml` tracks `dirty: text !== editor.currentText`. When
`currentFile` changes it only overwrites the `TextArea` when the buffer is not
dirty or not editing, so unsaved edits survive a controller refresh. Switching
files mid-edit is blocked in the controller (`_open_file_in_editor` warning).

### Editor window (QML)

`src/qml/windows/EditorWindow.qml` is a standalone top-level `Window` lazily
instantiated by [`qt-window-manager`](qt-window-manager.md) via
`windows.show_editor()` (the "Open Editor" button in `SkillDock.qml`, or when
`editor_open_requested` fires); it reports visibility via
`editor._handle_window_visibility(visible)`. `EditorPanel.qml` is a `SplitView`
placing the file tree pane (fuzzy search field + tree) on the left and the code
pane on the right, and renders `file_conflict` as a themed modal `Dialog` (mono
font, `fontSizeBase` = 12, square surfaces) whose buttons call
`_handle_conflict_keep` / `_handle_conflict_discard`.

### Highlighter bridge (`attachHighlighter`)

1. QML calls `editor.attachHighlighter(codeArea)` on `Component.onCompleted`.
2. `_text_document_wrapper` defensively reads the `textDocument` property — a
   `QQuickTextDocument` wrapper.
3. `wrapper.textDocument()` returns the `QTextDocument` a `QSyntaxHighlighter`
   needs. Both wrapper and document are retained (the wrapper owns the document);
   missing/unavailable documents are logged and ignored, never raised.
4. A `CodeHighlighter` is constructed on the document and set to `_language`;
   `_load_file_into_editor` swaps its language on every open.

## Function Reference

### Module-level helpers

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `detect_language(filepath: str) -> str` | `filepath` | language name or `"plain"` | `_EXT_TO_LANGUAGE.get(Path(filepath).suffix.lower(), "plain")` | None |

### Setup and properties

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `__init__(app: ProcooApp, parent: QObject \| None = None) -> None` | `app`; `parent` | `None` | `super().__init__(parent)`; stores `app` | None |
| `build(self) -> None` | — | `None` | Create model + state; `_refresh_file_tree` | Emits `file_tree_changed` |
| `start(self) -> None` | — | `None` | `_refresh_file_tree` | Emits `file_tree_changed` |
| `currentText.setter(value: str) -> None` | `value` | `None` | Store buffer; emit | Emits `current_file_changed` |
| `isFolderExpanded(path: str) -> bool` | `path` | expansion flag | `_file_model.is_folder_expanded` (QML delegate helper) | None |

### Slots: file tree

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_handle_file_click(path: str, is_folder: bool) -> None` | `path` relative to capabilities root; `is_folder` | `None` | Folder → toggle; file → `_open_file_in_editor(absolute)` | Schedules file load / emits tree change |
| `_handle_folder_toggle(path: str, expanded: bool) -> None` | `path`; `expanded` | `None` | `_file_model.set_folder_expanded`; emit | Emits `file_tree_changed` |
| `_handle_search_changed(text: str) -> None` @Slot(str) | `text` — search field content | `None` | Store `_search_text`; `_file_model.set_search`; emit | Emits `file_tree_changed` |
| `_handle_clear_search() -> None` @Slot | — | `None` | `_handle_search_changed("")` | Emits `file_tree_changed` |
| `_handle_open_automation(path: str) -> None` @Slot(str) | `path` relative to automations root | `None` | Emit `editor_open_requested`; `_open_file_in_editor(capabilities/automations/<path>/AUTOMATION.py)` | Emits `editor_open_requested`; schedules a load |

### Slots: edit / save / cancel / reload

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_handle_edit() -> None` | — | `None` | Warning if no file; else `_set_editing(True)` | Emits `toast_requested` / `edit_mode_changed` |
| `_handle_save(text: str) -> None` | `text` — QML buffer | `None` | Warning if no file; else spawn `_save(text)` | Schedules async write |
| `_handle_cancel() -> None` | — | `None` | Exit edit mode; spawn `_load_file_into_editor` | Emits `edit_mode_changed` |
| `_handle_reload() -> None` | — | `None` | Warning if no file; exit edit mode; spawn load | Emits `toast_requested` / `edit_mode_changed` |

### Slots: watcher, visibility & conflicts

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_handle_skill_files_changed() -> None` @Slot | — | `None` | No-op unless `_active`; else spawn `_refresh_from_watcher` | Schedules a task |
| `_handle_window_visibility(visible: bool) -> None` @Slot(bool) | `visible` | `None` | Store `_active`; on show re-emit a pending `file_conflict` or spawn `_refresh_from_watcher` | Emits `file_conflict`; schedules a task |
| `_handle_conflict_keep() -> None` @Slot | — | `None` | `"deleted"` → `_save(buffer)`; `"modified"` → `_disk_mtime = _conflict_mtime`; clear | Spawns a save; emits conflict cleared state |
| `_handle_conflict_discard() -> None` @Slot | — | `None` | `"deleted"` → clear buffer/emit `current_file_changed("")`; `"modified"` → reload from disk; clear | Emits `edit_mode_changed` / `current_file_changed`; schedules a load |

### Slots: highlighter bridge

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `attachHighlighter(area: QObject) -> None` | `area` — QML `TextArea` | `None` | Read `textDocument` wrapper → `QQuickTextDocument.textDocument()` → retain wrapper + document → build `CodeHighlighter`, set language | Logs and returns on missing document; never raises |
| `_text_document_wrapper(area: QObject) static -> Any \| None` | `area` | wrapper or `None` | `area.property("textDocument")` in a `try`; failure logs | Swallows exception |

### State: open / load / save

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_open_file_in_editor(filepath: str) -> None` | absolute `filepath` | `None` | Refuse while editing (warning); spawn `_load_file_into_editor` | Emits `toast_requested` |
| `_load_file_into_editor(filepath: str) async -> None` | absolute `filepath` | `None` | `await asyncio.to_thread(_read_file)` (content + mtime); set path/text/`_disk_mtime`/language; update highlighter; emit | Emits `toast_requested` on `OSError`/`UnicodeDecodeError`; emits `current_file_changed` |
| `_save(text: str) async -> None` | `text` | `None` | `await asyncio.to_thread(_write_file)` (returns mtime); update buffer + `_disk_mtime`; exit edit mode; toast; emit | Emits `toast_requested`, `edit_mode_changed`, `current_file_changed` |

### State: watcher reconciliation & conflicts

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_refresh_from_watcher() async -> None` | — | `None` | `await asyncio.to_thread(_file_model.rebuild, capabilities_dir, _search_text)`; emit; reconcile open file | Emits `file_tree_changed`; logs failure |
| `_reload_open_file_if_changed() async -> None` | — | `None` | Skip with no file / pending conflict; stat + read; prompt `"deleted"` / `"modified"`; equal content records mtime | Emits `file_conflict` |
| `_open_conflict(kind: str, path: str, mtime: float) -> None` | kind/path/mtime | `None` | Store conflict state; emit | Emits `file_conflict`; logs a warning |
| `_clear_conflict() -> None` | — | `None` | Reset `_conflict_path` / `_conflict_kind` / `_conflict_mtime` | None |

### State: edit mode & file tree

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_set_editing(editing: bool) -> None` | `editing` | `None` | No-op if unchanged; store + emit | Emits `edit_mode_changed` |
| `_refresh_file_tree() -> None` | — | `None` | `_file_model.rebuild(app.capabilities_dir, _search_text)`; emit | Emits `file_tree_changed` |

### Task & file helpers

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_read_file(path: str) static -> tuple[str, float]` | absolute `path` | content + `st_mtime` | `Path.read_text(utf-8)` then `stat` | Raises `OSError` / `UnicodeDecodeError` |
| `_write_file(path: str, text: str) static -> float` | `path`; `text` | `st_mtime` after write | `Path.write_text(utf-8)` then `stat` | Raises `OSError` |
| `_spawn(coro) -> None` | `coro` | `None` | `asyncio.ensure_future`; tracked in `_tasks`; done callbacks discard + log | Schedules on the running loop |
| `_log_task_failure(task) static -> None` | `task` | `None` | Ignore cancelled; log non-`None` exception | Logs error |

## Extension mappings

- **Language** (`_EXT_TO_LANGUAGE`, used by `detect_language` and the
  `CodeHighlighter`): `.py`/`.pyi` → `python`, `.md` → `markdown`, `.json` →
  `json`, `.yaml`/`.yml` → `yaml`, `.sh`/`.bash` → `bash`, `.js`/`.jsx`/`.ts`/
  `.tsx` → `javascript`, `.html`/`.xml` → `html`, `.css` → `css`, `.sql` → `sql`.
  Unknown extensions normalise to `"plain"` (`.toml`, `.java`, `.rs`, `.go`,
  `.c`/`.cpp`/`.h`/`.hpp`, `.cs`, `.swift`, `.kt`, `.rb`, `.php`, `.dockerfile`,
  `.makefile`).
- **Tree icon label** — owned by `FileTreeModel` (`models/file_tree_model.py`):
  a short extension label (`py`, `md`, `yaml`, …) per file, `"dir"` for folders,
  `"file"` fallback.

## Related

- [`qt-skill-controller`](qt-skill-controller.md) — its `skill_files_changed` watcher drives editor reconciliation.
- [`qt-ui`](qt-ui.md) — wires `skill.skill_files_changed` → `editor._handle_skill_files_changed`.
- [`qt-chat-items`](qt-chat-items.md) — chat card items.
