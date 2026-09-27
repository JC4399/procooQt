# Event server flow

How an external program triggers an event-driven automation over HTTP.

Related: [automation-server](../modules/automation-server.md), [automation-manager](../modules/automation-manager.md), [automation-runner](../modules/automation-runner.md), [automation-run-flow](automation-run-flow.md).

## Lifecycle

`ProcooQtUI.start()` → [AutomationController](../modules/qt-automation-controller.md)`start()`
→ `AutomationEventServer.start()` → `_start()` builds the aiohttp app and binds
`server.host`:`server.port` (default `127.0.0.1:12840`). `stop()` cleans up the
`AppRunner`.

## Request sequence

```
POST http://<host>:<port>/event/<event-name>
Authorization: Bearer <key>     (or X-Api-Key: <key>)
Content-Type: application/json

{ ... optional payload ... }
```

1. `_handle_event` checks auth (skipped when `auth.api_keys` is empty). Failure →
   `401`.
2. `_read_payload` parses an optional JSON object body. Invalid JSON → `400`.
3. `manager.get_event_automations(name)` returns matches; disabled ones are
   filtered out. No enabled match → `404`.
4. For each match: `runner.run(info, payload)` → `manager.record_run(...)` →
   `on_result(result)` (feeds notifications).
5. Response: `200 {"event": name, "results": [{"task","path","kind","message"}]}`.

## Routing

| Path | Method | Auth | Purpose |
|---|---|---|---|
| `/event/{name}` | POST | yes* | dispatch to matching automations |
| `/health` | GET | no | liveness probe |

\* required only when `auth.api_keys` is non-empty.

## Notes

- The handler awaits the automation, so the HTTP call returns the run's result.
  Long automations keep the request open; the runner's 1800s timeout applies.
- The server shares the qasync loop, so automations run on the GUI thread's loop
  and must not block (`ctx.ask` is async).

## Example

```
curl -X POST "http://127.0.0.1:12840/event/hello%20world" \
  -H "X-Api-Key: secret" -H "Content-Type: application/json" -d "{\"n\": 1}"
```
