# qt.ui — ProcooQtUI orchestrator

Source: `src/qt/ui.py`

## Purpose

Top-level UI object exposed to QML as the `ui` context property. Unlike the
Flet edition's six-mixin `ProcooFletUI`, it uses **composition**: it owns one
controller per panel plus the theme and notifier, wires their signals, builds
their models, and publishes every object to the QML root context. The Flet
mixins map to controllers here (`chat_panel` and `chat_loop` are merged into
[`qt-chat-controller`](qt-chat-controller.md)).

## Deliverables

- `ProcooQtUI(QObject)` owning `theme`, `notifier`, `session`, `chat`, `skill`,
  and `editor`.
- `_build_controllers()` — builds every controller's models and state.
- Eight QML context properties: `ui`, `backend`, `Theme`, `toasts`, `session`,
  `chat`, `skill`, `editor`.
- `start()` — startup hook invoked from `app.main` after the QML root loads.
- Cross-controller references and signal connections (toasts, session
  activation).

## Composition

```python
self.theme = Theme(self)
self.notifier = ErrorNotifier(self)
self.session = SessionController(app, self)
self.chat = ChatController(app, self)
self.skill = SkillController(app, self)
self.editor = EditorController(app, self)
self.chat.session = self.session      # cross-controller references
self.skill.session = self.session
self.skill.chat = self.chat
self.skill.notifier = self.notifier
```

Cross-controller signal connections made in `__init__`:

| Emitter signal | Connected slot |
|---|---|
| `session.toast_requested` | `notifier.toast_requested` |
| `session.active_session_changed` | `chat._handle_session_activated` |
| `session.active_session_changed` | `skill._handle_session_activated` |
| `chat.toast_requested` | `notifier.toast_requested` |
| `skill.toast_requested` | `notifier.toast_requested` |
| `editor.toast_requested` | `notifier.toast_requested` |

`active_session_changed` is the single activation bus: the
[session controller](qt-session-controller.md) emits it and the chat and skill
controllers react. `ErrorNotifier` fans the four `toast_requested` streams into
the `toasts` context property consumed by `ToastHost.qml`.

## Steps / Flow

### `__init__`

1. `super().__init__(parent)`.
2. Store `app` and `engine`; create `theme` and `notifier`.
3. Create the four controllers: `session`, `chat`, `skill`, `editor`.
4. Inject cross-controller references (`chat.session`, `skill.session`,
   `skill.chat`, `skill.notifier`).
5. Connect the toast and session-activation signals listed above.
6. `_build_controllers()` then `_expose_to_qml()`.

### `start` (from `app.py`)

`app.main` creates the `QApplication`, installs the qasync `QEventLoop`, creates
`ProcooQtUI`, loads `src/qml/Main.qml`, and — only if a root object loaded — calls
`ui.start()`. `start()` fans out to `session.start()`, `skill.start()`, and
`editor.start()`. The chat controller has no independent startup: it is driven
entirely by `active_session_changed`.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp, engine: QQmlApplicationEngine, parent: QObject \| None = None) -> None` | `app` backend subsystems; `engine` QML engine; `parent` optional Qt parent | `None` | theme/notifier → controllers → cross-refs → signal connections → `_build_controllers()` → `_expose_to_qml()` | Creates six child `QObject`s; connects signals |
| `def _build_controllers(self) -> None` | — | `None` | `session.build()` → `chat.build()` → `skill.build()` → `editor.build()` | Allocates models and per-session state |
| `@Slot() def start(self) -> None` | — | `None` | `session.start()` → `skill.start()` → `editor.start()` | Emits validation toasts; starts skill watcher |
| `def _expose_to_qml(self) -> None` | — | `None` | `engine.rootContext().setContextProperty(...)` for `ui`, `backend`, `Theme`, `toasts`, `session`, `chat`, `skill`, `editor` | Publishes objects to the QML root context |
