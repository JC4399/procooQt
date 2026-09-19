# qt.editor_controller — code editor & file tree

Source: `src/qt/editor_controller.py`

## Purpose

Drives the right sidebar's Editor tab: a read-only code editor backed by a QML
`TextArea`, a collapsible file tree rooted at the skills directory, and
Edit/Save/Cancel/Reload actions. It also attaches a `QSyntaxHighlighter` to the
`TextArea`'s text document. File reads and writes are offloaded with
`asyncio.to_thread` so the qasync loop never blocks. Behavior ports from the Flet
`editor_panel` mixin; QML stays view-only.

## Deliverables

- `FileTreeModel` (`editor.file_model`) — flattened file/folder rows.
- `EditorController` (`QObject`) with signals, `Q_PROPERTY` accessors, and `@Slot`
  handlers for file clicks, folder toggles, edit/save/cancel/reload.
- `attachHighlighter` bridge to `src/qt/highlighter.py`.
- `detect_language` + the `_EXT_TO_LANGUAGE` extension map.

## Signals & properties

| Signal | Payload | Emitted when |
|---|---|---|
| `file_tree_changed` | — | File tree rebuilt or a folder toggled; notifies `file_model`. |
| `current_file_changed` | `str` | Open/load/save/buffer update; notifies `currentFile`, `currentText`, `language`. |
| `edit_mode_changed` | `bool` | Edit mode toggled; notifies `editing`. |
| `toast_requested` | `str, str` | A message + toast level (`TOAST_INFO` / `TOAST_WARNING` / `TOAST_ERROR`). |

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
   `_language="plain"`, `_is_editing=False`, highlighter/document wrappers, `_tasks`.
2. `_refresh_file_tree()` emits `file_tree_changed`.

### Start (`start`)

`_refresh_file_tree()` re-walks `skill_manager.skills_dir` and emits.

### Open file (`_handle_file_click` → `_open_file_in_editor` → `_load_file_into_editor`)

1. Folders toggle expansion via `_handle_folder_toggle`; files resolve to an
   absolute path under `skill_manager.skills_dir`.
2. `_open_file_in_editor` refuses while `editing` (warning toast), else spawns
   `_load_file_into_editor`.
3. `_load_file_into_editor` `await asyncio.to_thread(Path.read_text)`; on success
   sets `_current_path` / `_current_text`, `detect_language`, updates the
   highlighter language, emits `current_file_changed`. Read errors toast.

### Edit mode / save / cancel / reload

- `_handle_edit` enters edit mode (warning when no file is open).
- `_handle_save(text)` writes the QML buffer to disk off-loop, exits edit mode,
  toasts success, and emits `current_file_changed`.
- `_handle_cancel` leaves edit mode and reloads the file from disk.
- `_handle_reload` leaves edit mode and reloads the file from disk.

### Dirty-state handling (QML)

`EditorPanel.qml` tracks `dirty: text !== editor.currentText`. When
`currentFile` changes it only overwrites the `TextArea` when the buffer is not
dirty or not editing, so unsaved edits survive a controller refresh. Switching
files mid-edit is blocked in the controller (`_open_file_in_editor` warning).

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
| `_handle_file_click(path: str, is_folder: bool) -> None` | `path` relative to skills root; `is_folder` | `None` | Folder → toggle; file → `_open_file_in_editor(absolute)` | Schedules file load / emits tree change |
| `_handle_folder_toggle(path: str, expanded: bool) -> None` | `path`; `expanded` | `None` | `_file_model.set_folder_expanded`; emit | Emits `file_tree_changed` |

### Slots: edit / save / cancel / reload

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_handle_edit() -> None` | — | `None` | Warning if no file; else `_set_editing(True)` | Emits `toast_requested` / `edit_mode_changed` |
| `_handle_save(text: str) -> None` | `text` — QML buffer | `None` | Warning if no file; else spawn `_save(text)` | Schedules async write |
| `_handle_cancel() -> None` | — | `None` | Exit edit mode; spawn `_load_file_into_editor` | Emits `edit_mode_changed` |
| `_handle_reload() -> None` | — | `None` | Warning if no file; exit edit mode; spawn load | Emits `toast_requested` / `edit_mode_changed` |

### Slots: highlighter bridge

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `attachHighlighter(area: QObject) -> None` | `area` — QML `TextArea` | `None` | Read `textDocument` wrapper → `QQuickTextDocument.textDocument()` → retain wrapper + document → build `CodeHighlighter`, set language | Logs and returns on missing document; never raises |
| `_text_document_wrapper(area: QObject) static -> Any \| None` | `area` | wrapper or `None` | `area.property("textDocument")` in a `try`; failure logs | Swallows exception |

### State: open / load / save

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_open_file_in_editor(filepath: str) -> None` | absolute `filepath` | `None` | Refuse while editing (warning); spawn `_load_file_into_editor` | Emits `toast_requested` |
| `_load_file_into_editor(filepath: str) async -> None` | absolute `filepath` | `None` | `await asyncio.to_thread(read_text, utf-8)`; set path/text/language; update highlighter; emit | Emits `toast_requested` on `OSError`/`UnicodeDecodeError`; emits `current_file_changed` |
| `_save(text: str) async -> None` | `text` | `None` | `await asyncio.to_thread(write_text, utf-8)`; update buffer; exit edit mode; toast; emit | Emits `toast_requested`, `edit_mode_changed`, `current_file_changed` |

### State: edit mode & file tree

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_set_editing(editing: bool) -> None` | `editing` | `None` | No-op if unchanged; store + emit | Emits `edit_mode_changed` |
| `_refresh_file_tree() -> None` | — | `None` | `_file_model.rebuild(skill_manager.skills_dir)`; emit | Emits `file_tree_changed` |

### Task helpers

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
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

- [`qt-skill-controller`](qt-skill-controller.md) — sibling right-sidebar tab.
- [`qt-chat-items`](qt-chat-items.md) — chat card items.
- Rebuild plan: [`../00-Rebuild-Plan.md`](../00-Rebuild-Plan.md).
- Flet counterpart: [`flet-editor-panel`](../../../wiki/modules/flet-editor-panel.md).
