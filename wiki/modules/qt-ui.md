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

The three per-window controllers (`session`, `chat`, `skill`) on the root
context belong to the **primary window**. Secondary windows get a fresh,
independent triple via `_build_window_bundle`, managed by
[`qt-window-manager`](qt-window-manager.md) and exposed as `windows`.

## Deliverables

- `ProcooQtUI(QObject)` owning `theme`, `notifier`, `session_bus`, `session`,
  `chat`, `skill`, `editor`, `automation`, `notification`, `subagent`, and
  `windows`.
- `_build_controllers()` — builds the primary controllers' models and state.
- `_build_window_bundle()` — builds a fresh `(context, session, chat, skill)`
  bundle for a secondary window on a child `QQmlContext`.
- `_wire_window()` / `_wire_automation()` — cross-controller references and
  signal connections.
- Eleven QML context properties: `ui`, `backend`, `Theme`, `toasts`, `session`,
  `chat`, `skill`, `editor`, `automation`, `notification`, `windows`.
- `start(window=None, frame_filter=None)` — startup hook invoked from `app.main`
  after the QML root loads; registers the primary window with `WindowManager`.

## Composition

```python
self.theme = Theme(self)
self.notifier = ErrorNotifier(self)
self.session_bus = SessionBus(self)               # shared across all windows
self.session = SessionController(app, self.session_bus, self)  # primary window
self.chat = ChatController(app, self)
self.skill = SkillController(app, self)
self.editor = EditorController(app, self)          # shared singleton
self.automation = AutomationController(app, self)
self.notification = NotificationController(app, self)
self.subagent = SubAgentController(app, self)
self.windows = WindowManager(
    app, engine, self._build_window_bundle, self.session_bus, qt_app, self
)
self._wire_window(self.session, self.chat, self.skill)
```

`_wire_window(session, chat, skill)` performs, for any window's triple:

| Emitter signal | Connected slot |
|---|---|
| `session.toast_requested` | `notifier.toast_requested` |
| `session.active_chat_changed` | `chat._handle_chat_activated` |
| `session.chat_switch_started` | `chat._handle_chat_switch_started` |
| `session.active_chat_changed` | `skill._handle_chat_activated` |
| `chat.chat_state_changed` | `session.refresh_chat_panels` |
| `chat.chat_tokens_changed` | `session.refresh_chat_tokens` |
| `chat.toast_requested` | `notifier.toast_requested` |
| `skill.toast_requested` | `notifier.toast_requested` |

It also sets `chat.session`, `session.chat`, `skill.session`, `skill.chat`, and
`skill.notifier`.

The shared [`SessionBus`](qt-session-bus.md) is passed to every
`SessionController` (primary and each secondary bundle) and to
[`WindowManager`](qt-window-manager.md). A session created or deleted anywhere
emits `sessions_changed`, and each controller's `refresh_sessions` resyncs that
window's title-bar list, so all open windows stay consistent.

`_wire_automation()` routes `editor.editor_open_requested →
windows.show_editor` so opening an automation file raises the editor window,
and connects the remaining shared signals.

The remaining shared connections are made in `__init__`:

| Emitter signal | Connected slot |
|---|---|
| `skill.skill_files_changed` | `editor._handle_skill_files_changed` |
| `automation.files_changed` | `editor._handle_skill_files_changed` |
| `editor.editor_open_requested` | `windows.show_editor` |
| `automation.result_ready` | `notification._handle_automation_result` |
| `automation.edit_automation_requested` | `editor._handle_open_automation` |
| `notification.edit_automation_requested` | `editor._handle_open_automation` |

`active_chat_changed` is the activation bus: the
[session controller](qt-session-controller.md) emits it when a panel activates a
chat, and the chat and skill controllers react. `chat_switch_started` is emitted
earlier (at the user action) so the panel loading overlay paints before the
off-thread hydration. `chat.chat_state_changed` lets the session controller push
per-panel runtime values as they change, and `chat.chat_tokens_changed` pushes
the token counts on every `token_usage` event (each LLM round-trip) without a
full runtime rebuild. `ErrorNotifier` fans every
`toast_requested` stream into the `toasts` context property consumed by
`ToastHost.qml`. The [skill controller](qt-skill-controller.md)'s
`skill_files_changed` and the [automation controller](qt-automation-controller.md)'s
`files_changed` are emitted on watchdog threads and queued to the
[editor controller](qt-editor-controller.md).

## QML view (context property consumers)

| Context | Consumed by |
|---|---|
| `session` | `SessionSelector.qml`; `SplitWorkspace.qml` (`maxPanels`, `panelOrder`, `panelCount`, `panelAt`, split/move slots) |
| `chat` | `ChatPanel.qml` (send/stop/approve per chat) |
| `skill` | `SkillDock.qml` (per-panel skill/tool config) |
| `windows` | `TitleBar.qml` (`new_window`), `Main.qml` / `ChatWindow.qml` (`show_editor` / `show_history`) |
| `editor` | `EditorWindow.qml` / `EditorPanel.qml` |
| `automation` / `notification` | `TitleBar.qml`, `AutomationPanel.qml`, `NotificationPanel.qml`, `NotificationHistoryWindow.qml` |
| `Theme` / `toasts` | All surfaces / `ToastHost.qml` |

## Steps / Flow

### `__init__`

1. `super().__init__(parent)`.
2. Store `app`, `engine`, and `qt_app`; create `theme`, `notifier`, and the
   shared `session_bus`.
3. Create the primary triple (passing the bus), the shared controllers, and
   `WindowManager` (passing the bus).
4. `_wire_window(primary triple)` then `_wire_automation()`.
5. `_build_controllers()` then `_expose_to_qml()`.

### `_build_window_bundle`

1. Create fresh `SessionController` (passing the shared `session_bus`) /
   `ChatController` / `SkillController`; set `session.prewarm_enabled = False` so
   secondary windows do not duplicate transcript pre-warming.
2. `_wire_window(...)` then `session.build()` / `chat.build()` / `skill.build()`.
3. Create `QQmlContext(self.engine.rootContext())` and set `session`, `chat`,
   `skill` on it.
4. Return `(context, session, chat, skill)` to `WindowManager`.

### `start` (from `app.py`)

`app.main` creates the `QApplication`, installs the qasync `QEventLoop`, creates
`ProcooQtUI(backend, engine, qt_app)`, loads `src/qml/Main.qml`, installs the
native frame, and calls `ui.start(root_window, frame_filter)`. `start()` fans out
to `session.start()`, `skill.start()`, `editor.start()`, `automation.start()`,
`control.start()`, `subagent.start()`, then `windows.register_primary(...)`.
After `loop.run_forever()` returns, `ui.shutdown()` flushes any debounced
session-layout write (`session.flush_layout`) before stopping every chat worker
(`chat.shutdown`).

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app, engine, qt_app=None, parent=None) -> None` | backend; QML engine; `QApplication`; parent | `None` | theme/notifier/session-bus → controllers → `WindowManager` → wiring → build → expose | Creates child `QObject`s; connects signals |
| `def _wire_window(self, session, chat, skill) -> None` | one window's triple | `None` | cross-refs + signal connections | Connects signals |
| `def _wire_automation(self) -> None` | — | `None` | wire automation/editor signals; route editor-open to `windows.show_editor` | Connects signals |
| `def _build_controllers(self) -> None` | — | `None` | build primary session/chat/skill/editor/notification/automation/control/subagent | Allocates models and state |
| `def _build_window_bundle(self) -> tuple[QQmlContext, SessionController, ChatController, SkillController]` | — | bundle | build + wire a fresh triple on a child context | Allocates models and state |
| `def start(self, window=None, frame_filter=None) -> None` | primary window; native-frame filter | `None` | controller starts → register primary | Starts watchers/scheduler/event/sub-agent servers |
| `def shutdown(self) -> None` | — | `None` | `session.flush_layout()` (persist any debounced layout) → `chat.shutdown()` | Stops worker threads |
| `def _expose_to_qml(self) -> None` | — | `None` | set root context properties | Publishes objects to QML |
