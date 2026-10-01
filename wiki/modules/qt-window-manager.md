# qt.window_manager — WindowManager

Source: `src/qt/window_manager.py`

## Purpose

Owns the set of open chat windows. Every window is a full app window bound to one
**session**; the primary window (`Main.qml`) is registered by `app.main`, and
secondary windows are created on demand (control server, or the title-bar
`+ Win` button). Each window gets a private `SessionController` /
`ChatController` / `SkillController` triple from
[`qt-ui`](qt-ui.md)'s `_build_window_bundle`, so its panels and tabs are
independent of every other window. The manager is exposed to QML as `windows`.

The shared editor and notification-history windows are singletons owned by the
primary window; secondary windows request them through
`show_editor` / `show_history`, which the primary window handles via its
`Connections { target: windows }` block.

## Deliverables

- `WindowManager(QObject)` exposed to QML as `windows`.
- `WindowRecord` dataclass bundling a window's session name, controllers, QML
  context/component, native-frame filter, and primary flag.
- Registry of secondary windows keyed by session name plus one primary record.
- Slots: `open_session`, `create_session`, `close_session`, `focus_session`,
  `new_window`, `show_editor`, `show_history`.
- Signals: `show_editor_requested`, `show_history_requested`, `windows_changed`.
- `delete_session(name)` — deletes a session, closes its window, and updates the
  primary window when it was the one showing the session.

## Window semantics

| Concept | Behaviour |
|---|---|
| Primary window | `Main.qml`, root-context controllers; closing quits the app |
| Secondary window | `ChatWindow.qml` on a child context with its own triple |
| Same session reopened | focuses the existing window instead of duplicating |
| Shared editor / history | shown by the primary window on request |
| Native frame | `native_frame.install` runs per secondary window |

## Steps / Flow

### `open_session(name)`

1. Return `False` if the session is unknown.
2. If the primary window currently shows the session, or a secondary window is
   registered for it, focus that window and return `True`.
3. Otherwise `_spawn_window(name)`.

### `_spawn_window(name)`

1. `_factory()` builds `(context, session, chat, skill)` and wires/builds them.
2. Create a `QQmlComponent` for `src/qml/windows/ChatWindow.qml` and
   `component.create(context)`; cast the result to `QWindow` / `QQuickWindow`.
3. Re-parent the controllers to the window so they are destroyed with it.
4. Connect `QQuickWindow.closing` to `_on_window_closing`.
5. `session.open_session(name)` and `skill.start()` (registers the window's skill
   watcher callback).
6. `native_frame.install(qt_app, window)`, store the record, `show()` + activate.

### `create_session(name, session_id)`

1. Strip and validate the name; if it already exists, open it and return its id.
2. `chat_store.create_session(name, session_id=...)`; open the new window.
3. Ensure the new session has an initial chat (`session.ensure_chat(0)`) so the
   window opens ready to use and the per-chat skill/model dock is active.
4. Return the stable session UUID.

### `delete_session(name)`

1. Return `False` if unknown.
2. If the primary window shows it, call `session._handle_delete_session(name)`.
3. If a secondary window shows it, delete via that window's session controller
   and close the window; otherwise delete directly from `ChatStore`.

### `_on_window_closing(name)`

Pops the record and calls `deleteLater()` on the window (the controllers are its
children and are collected with it).

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app, engine, factory, qt_app=None, parent=None) -> None` | backend app; QML engine; bundle factory; `QApplication`; parent | `None` | stores refs; empty registry | — |
| `def register_primary(self, session, chat, skill, window, frame_filter=None) -> None` | primary controllers + window + filter | `None` | sets `_primary`; emits `windows_changed` | — |
| `@Slot(str, result=bool) def open_session(self, name) -> bool` | session name | `True` if shown | focus existing else spawn | Creates a window on miss |
| `@Slot(str, str, result=str) def create_session(self, name, session_id="") -> str` | name; optional UUID | session UUID or `""` | upsert in `ChatStore` → open | Writes store; may create window |
| `@Slot(str) def close_session(self, name) -> None` | session name | `None` | close + drop secondary record | Closes a window |
| `@Slot(str) def focus_session(self, name) -> None` | session name | `None` | raise existing window | — |
| `@Slot() def new_window(self) -> None` | — | `None` | unique name → `create_session` | Creates session + window |
| `@Slot() def show_editor(self) -> None` | — | `None` | emit `show_editor_requested` | — |
| `@Slot() def show_history(self) -> None` | — | `None` | emit `show_history_requested` | — |
| `def delete_session(self, name) -> bool` | session name | `True` if deleted | primary/secondary/direct delete + close | Deletes store data |
| `def _spawn_window(self, name) -> WindowRecord \| None` | session name | new record or `None` | factory → QML create → wire → show | Creates QObject tree; installs native frame |
| `def _find_window(self, name) -> WindowRecord \| None` | session name | record or `None` | secondary registry then primary | — |
| `def _on_window_closing(self, name) -> None` | session name | `None` | drop record + `deleteLater` | Emits `windows_changed` |
| `@staticmethod def _focus(record) -> None` | record | `None` | `show` / `requestActivate` / `raise_` | — |
| `def _unique_name(self, base) -> str` | base name | unique name | suffix while colliding | — |

Authoring conventions live in [`../../AGENTS.md`](../../AGENTS.md).
