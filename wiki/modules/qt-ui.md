# qt.ui — ProcooQtUI orchestrator

Source: `src/qt/ui.py`

## Purpose

Top-level UI object exposed to QML as the `ui` context property. It uses
**composition**: it owns one controller per concern plus the theme and notifier,
wires their signals, builds their models, and publishes every object to the QML
root context. Chat rendering and streaming are both handled by
[`qt-chat-controller`](qt-chat-controller.md); the split workspace, session
selector, and per-panel view models are handled by
[`qt-session-controller`](qt-session-controller.md) and
[`qt-chat-panel-model`](qt-chat-panel-model.md).

## Deliverables

- `ProcooQtUI(QObject)` owning `theme`, `notifier`, `session`, `chat`, `skill`,
  and `editor`.
- `_build_controllers()` — builds every controller's models and state.
- Eight QML context properties: `ui`, `backend`, `Theme`, `toasts`, `session`,
  `chat`, `skill`, `editor`.
- `start()` — startup hook invoked from `app.main` after the QML root loads.
- Cross-controller references and signal connections (toasts, chat activation,
  state changes).

## Composition

```python
self.theme = Theme(self)
self.notifier = ErrorNotifier(self)
self.session = SessionController(app, self)
self.chat = ChatController(app, self)
self.skill = SkillController(app, self)
self.editor = EditorController(app, self)
self.chat.session = self.session      # cross-controller references
self.session.chat = self.chat
self.skill.session = self.session
self.skill.chat = self.chat
self.skill.notifier = self.notifier
```

Cross-controller signal connections made in `__init__`:

| Emitter signal | Connected slot |
|---|---|
| `session.toast_requested` | `notifier.toast_requested` |
| `session.active_chat_changed` | `chat._handle_chat_activated` |
| `session.chat_switch_started` | `chat._handle_chat_switch_started` |
| `session.active_chat_changed` | `skill._handle_chat_activated` |
| `chat.chat_state_changed` | `session.refresh_chat_panels` |
| `chat.toast_requested` | `notifier.toast_requested` |
| `skill.toast_requested` | `notifier.toast_requested` |
| `editor.toast_requested` | `notifier.toast_requested` |
| `skill.skill_files_changed` | `editor._handle_skill_files_changed` |

`active_chat_changed` is the activation bus: the
[session controller](qt-session-controller.md) emits it when a panel activates a
chat, and the chat and skill controllers react. `chat_switch_started` is emitted
earlier (at the user action) so the panel loading overlay paints before the
off-thread hydration. `chat.chat_state_changed` lets the session controller push
per-panel runtime values (busy/approval/tokens/config counts) as they change.
`ErrorNotifier` fans the four `toast_requested` streams into the `toasts`
context property consumed by `ToastHost.qml`. The
[skill controller](qt-skill-controller.md)'s `skill_files_changed` is emitted on
the watchdog thread and queued to the [editor controller](qt-editor-controller.md)
so it can reconcile the code editor window.

## QML view (context property consumers)

| Context | Consumed by |
|---|---|
| `session` | `SessionSelector.qml` (title bar); `SplitWorkspace.qml` (`panelCount`, `panelAt`, split/move slots) |
| `chat` | `ChatPanel.qml` (send/stop/approve per chat) |
| `skill` | `SkillDock.qml` (per-panel skill/tool config) |
| `Theme` / `toasts` | All surfaces / `ToastHost.qml` |

## Steps / Flow

### `__init__`

1. `super().__init__(parent)`.
2. Store `app` and `engine`; create `theme` and `notifier`.
3. Create the four controllers: `session`, `chat`, `skill`, `editor`.
4. Inject cross-controller references (`chat.session`, `session.chat`,
   `skill.session`, `skill.chat`, `skill.notifier`).
5. Connect the toast, activation, state-change, and skill-watcher signals above.
6. `_build_controllers()` then `_expose_to_qml()`.

### `start` (from `app.py`)

`app.main` creates the `QApplication`, installs the qasync `QEventLoop`, creates
`ProcooQtUI`, loads `src/qml/Main.qml`, and — only if a root object loaded — calls
`ui.start()`. `start()` fans out to `session.start()`, `skill.start()`, and
`editor.start()`.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp, engine: QQmlApplicationEngine, parent: QObject \| None = None) -> None` | `app` backend subsystems; `engine` QML engine; `parent` optional Qt parent | `None` | theme/notifier → controllers → cross-refs → signal connections → `_build_controllers()` → `_expose_to_qml()` | Creates six child `QObject`s; connects signals |
| `def _build_controllers(self) -> None` | — | `None` | `session.build()` → `chat.build()` → `skill.build()` → `editor.build()` | Allocates models and per-chat state |
| `@Slot() def start(self) -> None` | — | `None` | `session.start()` → `skill.start()` → `editor.start()` | Emits validation toasts; starts skill watcher; opens the workspace |
| `def _expose_to_qml(self) -> None` | — | `None` | `engine.rootContext().setContextProperty(...)` for `ui`, `backend`, `Theme`, `toasts`, `session`, `chat`, `skill`, `editor` | Publishes objects to the QML root context |
