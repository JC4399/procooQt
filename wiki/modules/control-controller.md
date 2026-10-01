# qt.control_controller — ControlController

Source: `src/qt/control_controller.py`

## Purpose

Lifecycle owner for the [control HTTP server](control-server.md). It reads the
`control_server` config, constructs a `ControlServer` bound to the app's
[`WindowManager`](qt-window-manager.md), and starts it during
[`qt-ui`](qt-ui.md)'s `start()`. It exposes no QML surface.

## Deliverables

- `ControlController(QObject)` owning one `ControlServer`.
- `build()` — construct the server from `ConfigManager` values.
- `start()` — start the server on the running qasync loop.
- `async stop()` — stop the server (used on shutdown).

## Steps / Flow

1. `ProcooQtUI.__init__` creates `ControlController(app, self.windows, self)`.
2. `_build_controllers()` calls `build()`, which reads
   `control_server_host`, `control_server_port`, and `control_server_api_keys`.
3. `ProcooQtUI.start()` calls `start()`, which starts the aiohttp server.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app, windows, parent=None) -> None` | backend; window manager; parent | `None` | store refs; `_server = None` | — |
| `def build(self) -> None` | — | `None` | construct `ControlServer` from config | Allocates server |
| `@Slot() def start(self) -> None` | — | `None` | `build()` if needed → `_server.start()` | Binds the control port |
| `async def stop(self) -> None` | — | `None` | `_server.stop()` | Releases socket |
