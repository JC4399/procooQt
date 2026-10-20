# qt.subagent_controller — SubAgentController

Source: `src/qt/subagent_controller.py`

## Purpose

Lifecycle owner for the local sub-agent HTTP server. It mirrors
[`control-controller`](control-controller.md): build the server from config, start
it with the app, and stop it on request. It is backend-only and is not exposed to
QML because sub-agents have no UI.

## Deliverables

- `SubAgentController(QObject)` with `build()`, `start()`, and `stop()`.
- Respects `subagent.enabled`; when disabled, no server is created.
- Passes `subagent.host`, `subagent.port`, `subagent.api_keys`, and
  `app.subagent_manager` to [`SubAgentServer`](subagent.md).

## Steps / Flow

1. `ProcooQtUI.__init__` creates `self.subagent = SubAgentController(app, self)`.
2. `build()` returns early when `subagent.enabled` is false; otherwise constructs
   the server.
3. `start()` builds lazily if needed, then calls `SubAgentServer.start()` on the
   qasync loop.
4. `stop()` awaits `SubAgentServer.stop()`, releasing the socket.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp, parent=None) -> None` | backend; Qt parent | `None` | store app; `_server=None` | — |
| `def build(self) -> None` | — | `None` | read config; construct `SubAgentServer` | Logs when disabled |
| `@Slot() def start(self) -> None` | — | `None` | build if needed; start server | Binds the port |
| `async def stop(self) -> None` | — | `None` | stop server | Releases the socket |

## See also

- [subagent](subagent.md) — manager and HTTP endpoints.
- [qt-ui](qt-ui.md) — controller composition.
- [subagent-flow](../flows/subagent-flow.md) — runtime sequence.
