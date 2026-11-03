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
After an external create or delete it emits
[`SessionBus.sessions_changed`](qt-session-bus.md) so every open window refreshes
its title-bar session list.

The shared editor and notification-history windows are singletons owned by the
manager itself. They are lazily instantiated on the engine root context from
their own QML files (never declared inside `Main.qml`, so they have no implicit
transient parent) and cached; any window requests them through
`show_editor` / `show_history`.

## Deliverables

- `WindowManager(QObject)` exposed to QML as `windows`.
- `WindowRecord` dataclass bundling a window's session name, controllers, QML
  context/component, native-frame filter, and primary flag.
- `ToolWindowRecord` dataclass bundling a cached singleton window and its
  component.
- Registry of secondary windows keyed by session name plus one primary record
  and the two cached tool-window records.
- Slots: `open_session`, `create_session`, `close_session`, `focus_session`,
  `new_window`, `show_editor`, `show_history`.
- Signal: `windows_changed`.
- `delete_session(name)` — deletes a session, closes its window, and updates the
  primary window when it was the one showing the session.
- Holds the shared [`SessionBus`](qt-session-bus.md); emits `sessions_changed`
  after an external create or delete so all windows resync.

## Window semantics

| Concept | Behaviour |
|---|---|
| Primary window | `Main.qml`, root-context controllers; closing quits the app |
| Secondary window | `ChatWindow.qml` on a child context with its own triple |
| Same session reopened | focuses the existing window instead of duplicating |
| Shared editor / history | lazily created + cached by the manager; independent top-level windows |
| Native frame | `native_frame.install` runs per secondary window; tool windows keep their OS title bar |

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
   watcher callback). Secondary windows have `prewarm_enabled = False`, so opening
   a window does not duplicate transcript pre-warming.
6. `native_frame.install(qt_app, window)`, store the record, `show()` + activate.

### `create_session(name, session_id)`

1. Strip and validate the name; if it already exists, open it and return its id.
2. `chat_store.create_session(name, session_id=...)`.
3. Emit [`SessionBus.sessions_changed`](qt-session-bus.md) so every other open
   window adds the new session to its title bar.
4. Open the new window and ensure the session has an initial chat
   (`session.ensure_chat(0)`) so it opens ready to use and the per-chat
   skill/model dock is active.
5. Return the stable session UUID.

### `delete_session(name)`

1. Return `False` if unknown.
2. Pop the secondary record for the session, if any.
3. If a secondary window shows it, delete through that window's session
   controller (which emits the [session bus](qt-session-bus.md)) and close the
   window.
4. Else if the primary window shows it, delete through the primary session
   controller (which emits the bus).
5. Else delete directly from `ChatStore` and emit the bus explicitly, so every
   remaining window drops the stale session row.

### `_on_window_closing(name)`

Pops the record, calls `record.chat.shutdown_window()` to stop that window's
workers and drop its agents/models, then calls `deleteLater()` on the window (the
controllers are its children and are collected with it). `close_session` and
`delete_session` call `shutdown_window()` directly before closing because they
pop the record first.

### `show_editor()` / `show_history()`

1. Pass the cached `ToolWindowRecord` (or `None`) and the window's QML path to
   `_show_tool_window`.
2. On first call the window does not exist: `_create_tool_window` instantiates it
   with `QQmlComponent(engine, path).create()` on the engine root context
   (`editor`, `toasts`, `Theme`, `notification` resolve from root context
   properties), casts it to `QWindow`, and emits `windows_changed`.
3. `show()` + `requestActivate()` the window. Closing it only hides it (the QML
   `Window` stays cached), so a later request re-shows the same instance.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app, engine, factory, bus, qt_app=None, parent=None) -> None` | backend app; QML engine; bundle factory; session bus; `QApplication`; parent | `None` | stores refs; empty registry | — |
| `def register_primary(self, session, chat, skill, window, frame_filter=None) -> None` | primary controllers + window + filter | `None` | sets `_primary`; emits `windows_changed` | — |
| `@Slot(str, result=bool) def open_session(self, name) -> bool` | session name | `True` if shown | focus existing else spawn | Creates a window on miss |
| `@Slot(str, str, result=str) def create_session(self, name, session_id="") -> str` | name; optional UUID | session UUID or `""` | upsert in `ChatStore` → emit bus → open → `ensure_chat` | Writes store; may create window; emits `SessionBus.sessions_changed` |
| `@Slot(str) def close_session(self, name) -> None` | session name | `None` | close + drop secondary record | Closes a window |
| `@Slot(str) def focus_session(self, name) -> None` | session name | `None` | raise existing window | — |
| `@Slot() def new_window(self) -> None` | — | `None` | unique name → `create_session` | Creates session + window |
| `@Slot() def show_editor(self) -> None` | — | `None` | show cached editor window, create on first use | Lazily creates a window; emits `windows_changed` |
| `@Slot() def show_history(self) -> None` | — | `None` | show cached history window, create on first use | Lazily creates a window; emits `windows_changed` |
| `def delete_session(self, name) -> bool` | session name | `True` if deleted | secondary controller / primary controller / direct store delete + close | Deletes store data; emits `SessionBus.sessions_changed` |
| `def _spawn_window(self, name) -> WindowRecord \| None` | session name | new record or `None` | factory → QML create → wire → show | Creates QObject tree; installs native frame |
| `def _show_tool_window(self, record, qml_path) -> ToolWindowRecord \| None` | cached record or `None`; QML path | shown record or `None` | create if missing → `show`/`requestActivate` | May create a window; emits `windows_changed` |
| `def _create_tool_window(self, qml_path) -> ToolWindowRecord \| None` | QML path | new record or `None` | `QQmlComponent.create()` on root context | Creates a QObject tree |
| `def _find_window(self, name) -> WindowRecord \| None` | session name | record or `None` | secondary registry then primary | — |
| `def _on_window_closing(self, name) -> None` | session name | `None` | shutdown window chats → drop record + `deleteLater` | Emits `windows_changed` |
| `@staticmethod def _focus(record) -> None` | record | `None` | `show` / `requestActivate` / `raise_` | — |
| `def _unique_name(self, base) -> str` | base name | unique name | suffix while colliding | — |

Authoring conventions live in [`../../AGENTS.md`](../../AGENTS.md).
