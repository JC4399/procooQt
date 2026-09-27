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
  `editor`, `editor_chat`, `automation`, and `notification`.
- `_build_controllers()` — builds every controller's models and state.
- Eleven QML context properties: `ui`, `backend`, `Theme`, `toasts`, `session`,
  `chat`, `skill`, `editor`, `editorChat`, `automation`, `notification`.
- `start()` — startup hook invoked from `app.main` after the QML root loads.
- Cross-controller references and signal connections (toasts, chat activation,
  state changes, automation results, debug-open).

## Composition

```python
self.theme = Theme(self)
self.notifier = ErrorNotifier(self)
self.session = SessionController(app, self)
self.chat = ChatController(app, self)
self.skill = SkillController(app, self)
self.editor = EditorController(app, self)
self.editor_chat = EditorChatController(app, self)
self.automation = AutomationController(app, self)
self.notification = NotificationController(app, self)
self.chat.session = self.session      # cross-controller references
self.session.chat = self.chat
self.skill.session = self.session
self.skill.chat = self.chat
self.skill.notifier = self.notifier
self.editor_chat.editor = self.editor
self.editor_chat.session = self.session
self.editor_chat.chat = self.chat
```

Cross-controller signal connections made in `__init__`:

| Emitter signal | Connected slot |
|---|---|
| `session.toast_requested` | `notifier.toast_requested` |
| `session.active_chat_changed` | `chat._handle_chat_activated` |
| `session.chat_switch_started` | `chat._handle_chat_switch_started` |
| `session.active_chat_changed` | `skill._handle_chat_activated` |
| `chat.chat_state_changed` | `session.refresh_chat_panels` |
| `chat.chat_state_changed` | `editor_chat._handle_state_changed` |
| `chat.token_counts_changed` | `editor_chat._handle_token_counts` |
| `chat.toast_requested` | `notifier.toast_requested` |
| `skill.toast_requested` | `notifier.toast_requested` |
| `editor.toast_requested` | `notifier.toast_requested` |
| `editor_chat.toast_requested` | `notifier.toast_requested` |
| `automation.toast_requested` | `notifier.toast_requested` |
| `skill.skill_files_changed` | `editor._handle_skill_files_changed` |
| `automation.files_changed` | `editor._handle_skill_files_changed` |
| `automation.result_ready` | `notification._handle_automation_result` |
| `automation.edit_automation_requested` | `editor._handle_open_automation` |
| `notification.edit_automation_requested` | `editor._handle_open_automation` |

`active_chat_changed` is the activation bus: the
[session controller](qt-session-controller.md) emits it when a panel activates a
chat, and the chat and skill controllers react. `chat_switch_started` is emitted
earlier (at the user action) so the panel loading overlay paints before the
off-thread hydration. `chat.chat_state_changed` lets the session controller push
per-panel runtime values (busy/approval/tokens/config counts) as they change.
`ErrorNotifier` fans every `toast_requested` stream into the `toasts`
context property consumed by `ToastHost.qml`. The
[skill controller](qt-skill-controller.md)'s `skill_files_changed` and the
[automation controller](qt-automation-controller.md)'s `files_changed` are
emitted on watchdog threads and queued to the
[editor controller](qt-editor-controller.md) so it can reconcile the code editor
window. `automation.result_ready` feeds the
[notification controller](qt-notification-controller.md), and both the
automation Edit and notification Debug actions open the matching automation file
via `editor._handle_open_automation`.

## QML view (context property consumers)

| Context | Consumed by |
|---|---|
| `session` | `SessionSelector.qml` (title bar); `SplitWorkspace.qml` (`panelCount`, `panelAt`, split/move slots) |
| `chat` | `ChatPanel.qml` (send/stop/approve per chat) |
| `skill` | `SkillDock.qml` (per-panel skill/tool config) |
| `editor` / `editorChat` | `EditorWindow.qml` / `EditorPanel.qml` / `EditorChatPanel.qml` |
| `automation` / `notification` | `TitleBar.qml` (tabs + badges), `AutomationPanel.qml`, `NotificationPanel.qml`, `NotificationHistoryWindow.qml` |
| `Theme` / `toasts` | All surfaces / `ToastHost.qml` |

## Steps / Flow

### `__init__`

1. `super().__init__(parent)`.
2. Store `app` and `engine`; create `theme` and `notifier`.
3. Create the controllers: `session`, `chat`, `skill`, `editor`, `editor_chat`,
   `automation`, `notification`.
4. Inject cross-controller references (`chat.session`, `session.chat`,
   `skill.session`, `skill.chat`, `skill.notifier`, `editor_chat.editor`,
   `editor_chat.session`).
5. Connect the toast, activation, state-change, watcher, result, and debug-open
   signals above.
6. `_build_controllers()` then `_expose_to_qml()`.

### `start` (from `app.py`)

`app.main` creates the `QApplication`, installs the qasync `QEventLoop`, creates
`ProcooQtUI`, loads `src/qml/Main.qml`, and — only if a root object loaded — calls
`ui.start()`. `start()` fans out to `session.start()`, `skill.start()`,
`editor.start()`, and `automation.start()` (watcher + scheduler + event server).

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp, engine: QQmlApplicationEngine, parent: QObject \| None = None) -> None` | `app` backend subsystems; `engine` QML engine; `parent` optional Qt parent | `None` | theme/notifier → controllers → cross-refs → signal connections → `_build_controllers()` → `_expose_to_qml()` | Creates nine child `QObject`s; connects signals |
| `def _build_controllers(self) -> None` | — | `None` | `session.build()` → `chat.build()` → `skill.build()` → `editor.build()` → `editor_chat.build()` → `notification.build()` → `automation.build()` | Allocates models and per-chat state |
| `@Slot() def start(self) -> None` | — | `None` | `session.start()` → `skill.start()` → `editor.start()` → `automation.start()` | Emits validation toasts; starts watchers/scheduler/event server; opens the workspace |
| `def _expose_to_qml(self) -> None` | — | `None` | `engine.rootContext().setContextProperty(...)` for `ui`, `backend`, `Theme`, `toasts`, `session`, `chat`, `skill`, `editor`, `editorChat`, `automation`, `notification` | Publishes objects to the QML root context |
