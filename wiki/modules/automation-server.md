# automation.server — AutomationEventServer

Source: `procooQt/src/automation/server.py`

## Purpose

Receives external HTTP events and runs every enabled event-driven automation
registered for that event name. It runs on the qasync loop (sharing the app's
single loop with the scheduler and UI) and binds `127.0.0.1` by default. When
`auth.api_keys` is non-empty, requests must present a matching key.

## Deliverables

- `AutomationEventServer(host, port, api_keys, manager, runner, on_result)`.
- `start()` / `stop()` lifecycle managing an aiohttp `AppRunner` + `TCPSite`.
- Routes: `POST /event/{name}`, `GET /health`.
- API-key authentication (`Authorization: Bearer <key>` or `X-Api-Key`).
- JSON result summary.

## Endpoints

| Method | Path | Behaviour |
|---|---|---|
| `POST` | `/event/{name}` | Run enabled automations whose `event` matches `name` |
| `GET` | `/health` | `{"status": "ok"}` (always open) |

`POST /event/{name}` responses:

| Status | When |
|---|---|
| `200` | `{"event": name, "results": [{"task", "path", "kind", "message"}]}` |
| `400` | body present but not valid JSON |
| `401` | keys configured and missing/wrong |
| `404` | no enabled automation matches the event |

An optional JSON object body is passed to the automation as `ctx.payload`.

## Steps / Flow

1. `start()` → `ensure_future(_start())`; `_start` builds the aiohttp app, runner,
   and site, then logs the bind address + auth mode.
2. `_handle_event`: authorize → read payload → find enabled matches → for each,
   `runner.run(info, payload)`, `manager.record_run(...)`, `on_result(result)` →
   return the JSON summary.
3. `stop()` → `AppRunner.cleanup()` and cancel the startup task.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, host, port, api_keys, manager, runner, on_result) -> None` | bind + subsystem refs | `None` | store refs | — |
| `def start(self) -> None` | — | `None` | schedule `_start`; log failures via done-callback | Starts server task |
| `async def stop(self) -> None` | — | `None` | cleanup runner; cancel task | Releases socket |
| `async def _start(self) -> None` | — | `None` | build app + routes + site | Logs listening/auth |
| `async def _handle_health(self, request) -> Response` | request | `{"status":"ok"}` | — | — |
| `async def _handle_event(self, request) -> Response` | request | JSON summary / 4xx | auth → payload → matches → run | Runs automations; records state |
| `async def _read_payload(self, request) -> dict \| None` | request | payload or `None` | `request.json()` guarded | — |
| `_authorized(self, request) -> bool` | request | `bool` | keys empty ⇒ `True`; else match header | — |
| `_extract_key(request) static -> str` | request | key string | Bearer or `X-Api-Key` | — |

## See also

- [automation-manager](automation-manager.md) — event lookup + run state.
- [automation-runner](automation-runner.md) — execution.
- [event-server-flow](../flows/event-server-flow.md) — end-to-end sequence.
- [qt-automation-controller](qt-automation-controller.md) — starts the server.
