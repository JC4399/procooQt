# control.server — ControlServer

Source: `src/control/server.py`

## Purpose

HTTP server used by external tools (e.g. the Obsidian plugin) to create, open,
and delete Procoo sessions and their windows. It is separate from the automation
[event server](automation-server.md) so each can bind its own port and keys. It
runs on the qasync loop, so handlers call the
[`WindowManager`](qt-window-manager.md) directly. Requests are authenticated with
`Authorization: Bearer <key>` or `X-Api-Key` when `control_server.api_keys`
(resolved via `ConfigManager.control_server_api_keys`, falling back to
`auth.api_keys`) is non-empty.

## Deliverables

- `ControlServer` with `start()` / `stop()` lifecycle mirroring the automation
  event server.
- Endpoints: `GET /health`, `POST /sessions`, `POST /sessions/open`,
  `POST /sessions/delete`.
- Name normalisation (`_sanitize_name`) and id-or-name session resolution
  (`_resolve_session`).

## Endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/health` | — | `{"status": "ok"}` |
| `POST` | `/sessions` | `{id?, name?}` | `{id, name, created, open}` |
| `POST` | `/sessions/open` | `{id?, name?}` | `{id, name, open}`; `404` if unknown |
| `POST` | `/sessions/delete` | `{id?, name?}` | `{id, name, deleted}`; `404` if unknown |

`POST /sessions` is an upsert: a known `id` (or a name collision) opens the
existing session and returns `created: false`; otherwise a new session is
created and opened. The returned `id` is authoritative — the caller should store
it (e.g. in the note markup) even if it supplied a different one.

## Steps / Flow

### `POST /sessions`

1. Authorise; parse JSON (invalid body → `400`).
2. Sanitise the name; if `id` resolves to a session, open it → `created: false`.
3. Else if the name exists, open it → `created: false`.
4. Else `WindowManager.create_session(name, session_id=id)` and return the
   created session's id with `created: true`.

### `POST /sessions/open` and `/sessions/delete`

1. Authorise; parse JSON.
2. `_resolve_session` (id first, then name) → `404` when unknown.
3. `open_session(name)` / `delete_session(name)` and return the record id+name.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, host, port, api_keys, chat_store, windows) -> None` | bind + auth + stores | `None` | store config | — |
| `def start(self) -> None` | — | `None` | schedule `_start` | Binds the TCP site |
| `async def stop(self) -> None` | — | `None` | cleanup runner + cancel task | Releases socket |
| `async def _start(self) -> None` | — | `None` | routes → `AppRunner.setup` → `TCPSite.start` | Logs auth mode |
| `async def _handle_health(self, request)` | request | JSON `{"status":"ok"}` | — | — |
| `async def _handle_create_session(self, request)` | JSON body | JSON result | upsert-and-open | May create session + window |
| `async def _handle_open_session(self, request)` | JSON body | JSON result / 404 | resolve → open | Opens/focuses a window |
| `async def _handle_delete_session(self, request)` | JSON body | JSON result / 404 | resolve → delete | Deletes store data + window |
| `def _resolve_session(self, payload) -> dict \| None` | payload | session record | id then name lookup | — |
| `@staticmethod def _sanitize_name(value) -> str` | raw name | normalised name | collapse/trim/truncate 60 | — |
| `async def _read_payload(self, request) -> dict \| None` | request | dict / `None` | parse optional JSON object | — |
| `def _authorized(self, request) -> bool` | request | bool | disabled or key match | — |
| `@staticmethod def _extract_key(request) -> str` | request | key string | Bearer / `X-Api-Key` | — |
