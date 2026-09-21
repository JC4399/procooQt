# qt.session_controller — session sidebar & lifecycle

Source: `src/qt/session_controller.py`

## Purpose

Owns the session sidebar model and the per-session [`SessionState`](qt-session-state.md)
registry. Implements session creation, switching, deletion, persistence, and
hydration. All panel interaction is exposed to QML through typed
`Signal`, `Slot`, and `Property` members.

## Deliverables

- `SessionStatus` string constants and the `_STATUS_COLORS` lookup.
- `session_model` property (`SessionListModel`) — folders + enriched session
  tiles for `SessionPanel.qml`.
- `state()` registry of `SessionState` objects, one per live session.
- Slots for create/click/delete session, create/delete folder, folder
  expansion, and drop-on-folder.
- Persistence helpers (`_create_stored_session`,
  `_save_current_session_for`, `_session_save_snapshot`, `_build_context_snapshot`).
- Hydration helpers (`_hydrate_session`, `_create_manager_session`) and the
  switching/auto-select/delete flows.
- Single-pass sidebar reload (`_collect_summaries` / `_apply_summaries`), used
  off-thread by `_switch_to_session` and synchronously by `_refresh_model`.

## Signals

| Signal | Payload | Meaning |
|---|---|---|
| `sessions_changed` | — | Sidebar rows changed (also notifies `session_model`) |
| `active_session_changed` | `str` | Active session id, or `""` when none |
| `session_switch_started` | `str` | A switch was requested (tile click / new / startup / delete) — emitted **before** the save + sidebar reload so the chat loading overlay can paint immediately |
| `toast_requested` | `str, str` | Message + toast level (`TOAST_ERROR` / `TOAST_WARNING`) |
| `new_folder_requested` | — | Ask QML to open the new-folder dialog |

## Properties

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `session_model` | `SessionListModel` | `sessions_changed` | Flattened folder/session rows exposed as `session.session_model` |

## `SessionStatus`

| Status | Meaning |
|---|---|
| `EMPTY` | No stored messages |
| `RUNNING` | Busy with a generation |
| `WAITING` | Busy, awaiting tool approval |
| `FINISHED` | Has messages, idle |
| `ERROR` | Reserved error state |

`statusColor(status)` maps a status string to the matching `COLOR_SESSION_*`
theme constant (default `COLOR_SESSION_EMPTY`); `SessionPanel.qml` calls it to
paint each tile's dot.

## Steps / Flow

### New session (`_handle_new_session`)

1. `_generate_unique_session_id()` (timestamp, suffixed if taken).
2. `_create_stored_session(id)` writes an empty record.
3. Prepend the id to `session_ids`; emit `session_switch_started(id)`; then
   `_spawn(_switch_to_session(id))`.

### Switch (`_switch_to_session`)

1. Set `active_session_id`; create/get its `SessionState`.
2. Snapshot the previous session on the GUI thread (`_session_save_snapshot`) and
   `await asyncio.to_thread(_save_current_session_for, old_sid, snapshot)`.
3. `await asyncio.to_thread(_collect_summaries)` (single-pass disk read) →
   `_apply_summaries(...)` (GUI thread) → emit `active_session_changed` (chat +
   skill react).
4. `await asyncio.to_thread(session_store.load_session)`; if the session is not
   live but has stored messages, `await _hydrate_session(...)`.
5. After each `await`, abort when `active_session_id` no longer matches, so a
   newer switch supersedes an in-flight one.

Blocking disk I/O runs off the GUI thread so the chat loading overlay (turned on
by `session_switch_started`) keeps painting.

### Delete (`_delete_session_by_id`)

1. Pop the `SessionState`; `_cancel_pending_operations` (deny tool, release
   approval, cancel task).
2. `session_manager.remove_session` + `session_store.delete_session`.
3. Remove from `session_ids`; if it was active, select the first remaining id (and
   emit `session_switch_started`) or emit `active_session_changed("")`.
4. `_refresh_model()`; switch to the replacement when applicable.

### Hydration (`_hydrate_session` → `_create_manager_session`)

1. Return the live session if `session_manager` already has it.
2. Load the stored record off-thread (toast + `None` if missing).
3. Read `skills_config.primary` / `.secondary`; create the live session through
   `_create_manager_session` **on a worker thread** via `asyncio.to_thread`. It
   calls `session_manager.create_session` (now synchronous) with model config,
   loaded skill contents, tool functions/config, limits, and `initial_messages` —
   Agent construction and skill/AST loading no longer block the GUI thread.
4. On failure wrap in `SessionError` (log `detail`, toast `brief`).
5. `await session.refresh_estimated()` (offloaded); backfill and save
   `context_snapshot` off-thread if absent.

### Auto-select (`_auto_select_session`)

- If sessions exist, emit `session_switch_started` and switch to `session_ids[0]`.
- Otherwise create a timestamp session, mark it active, emit
  `session_switch_started`, refresh, and emit `active_session_changed`.

### Folder operations

`_handle_create_folder` / `_handle_delete_folder` / `_handle_drop_on_folder`
delegate to `session_store`, map `ValueError` to an error toast, and call
`_refresh_model`. `_handle_folder_expansion` records expansion on the model and
refreshes; `is_folder_expanded` reads it back for QML.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def build(self) -> None` | — | `None` | create `SessionListModel` → init `_states`/`_tasks`/`session_ids` → `_refresh_model()` | Emits `sessions_changed` |
| `@Property(QObject, notify=sessions_changed) def session_model(self) -> SessionListModel` | — | The list model | returns `_session_model` | Notify signal is `sessions_changed` |
| `def state(self, session_id: str) -> SessionState` | `session_id` | The session's state | create-on-demand into `_states` | Inserts a new `SessionState` |
| `@Slot() def start(self) -> None` | — | `None` | `_emit_validation_issues()` → `_auto_select_session()` | Toasts; emits `active_session_changed` |
| `@Slot() def _handle_new_session(self) -> None` | — | `None` | unique id → `_create_stored_session` → prepend id → emit `session_switch_started` → `_spawn(_switch_to_session)` | Writes store; emits signal |
| `@Slot(str) def _handle_session_click(self, session_id: str) -> None` | `session_id` | `None` | no-op on empty/same-as-active → emit `session_switch_started` → `_spawn(_switch_to_session)` | Emits signal; switches session |
| `@Slot(str) def _handle_delete_session(self, session_id: str) -> None` | `session_id` | `None` | no-op on empty → `_delete_session_by_id` | Deletes store + model rows |
| `@Slot() def _handle_new_folder(self) -> None` | — | `None` | emits `new_folder_requested` | QML opens the dialog |
| `@Slot(str) def _handle_create_folder(self, name: str) -> None` | `name` | `None` | strip → empty toast → `session_store.create_folder` → expand + refresh | `ValueError` → error toast |
| `@Slot(str) def _handle_delete_folder(self, name: str) -> None` | `name` | `None` | no-op on empty → `session_store.delete_folder` → refresh | `ValueError` → error toast |
| `@Slot(str, str) def _handle_drop_on_folder(self, session_id: str, folder: str) -> None` | `session_id`; `folder` (empty = unfiled) | `None` | `set_session_folder(id, folder or None)` → refresh | `ValueError` → error toast |
| `@Slot(str, bool) def _handle_folder_expansion(self, name: str, expanded: bool) -> None` | folder `name`, `expanded` | `None` | model `set_folder_expansion` → `_refresh_model` | Emits `sessions_changed` |
| `@Slot(str, result=bool) def is_folder_expanded(self, name: str) -> bool` | folder `name` | Expanded flag | model `is_expanded` | — |
| `@Slot(str, result=str) def statusColor(self, status: str) -> str` | status string | Hex color | `_STATUS_COLORS.get(status, COLOR_SESSION_EMPTY)` | — |
| `def _refresh_model(self) -> None` | — | `None` | `_collect_summaries()` → `_apply_summaries()` | Emits `sessions_changed` |
| `def _collect_summaries(self) -> tuple[list[dict], list[str]]` | — | `(enriched, folders)` | snapshot `_states` → `load_all_sessions()` (one parse/file) → `_enrich_session` → `list_folders()` | Thread-safe (touches no Qt objects) |
| `def _apply_summaries(self, enriched: list[dict], folders: list[str]) -> None` | enriched summaries; folders | `None` | rebuild `session_ids` → `set_sessions(...)` → emit | GUI thread only; emits `sessions_changed` |
| `def _enrich_session(self, stored: dict, states: dict) -> dict` | full stored dict; states snapshot | Summary + `title`/`status` | derive title/status from the already-loaded data | No extra disk read |
| `@staticmethod def _derive_session_title(sess: dict) -> str` | stored session | Title | first user message, first 30 chars + `...`, else id[:15] | — |
| `def _derive_session_status(self, sid: str, stored: dict \| None, states: dict) -> str` | id, stored data, states snapshot | `SessionStatus` | busy → `WAITING`/`RUNNING`; else `EMPTY`/`FINISHED` | Reads the passed snapshot |
| `@staticmethod def _build_context_snapshot(session: Any) -> dict` | live session | Snapshot dict | grabs `sys_prompt`, `_pending_sys_message`, skills, `_tools`, `_tool_config` | — |
| `def _create_stored_session(self, session_id: str) -> None` | id | `None` | build empty record with `skills_config`/`messages`/timestamps → save | Writes store |
| `def _session_save_snapshot(self, session_id: str) -> tuple[list[dict], dict] \| None` | id | `(messages, context_snapshot)` or `None` | capture live messages + context on the GUI thread | — |
| `def _save_current_session_for(self, session_id: str, snapshot=None) -> None` | id; optional precomputed snapshot | `None` | (if no snapshot) capture → load stored → replace `messages`, `message_count`, `context_snapshot` → `save_session` (atomic) | Writes store; safe on a worker thread with a snapshot |
| `def _generate_unique_session_id(self) -> str` | — | Unique id | timestamp base, suffix while colliding with `list_session_ids()`/`session_ids` | — |
| `async def _hydrate_session(self, session_id: str, stored: dict \| None = None) -> Any` | id; optional stored data | Live session or `None` | existing → off-thread load → off-thread `_create_manager_session` → `refresh_estimated` → off-thread snapshot save | `SessionError` path logs + toasts; never blocks the GUI thread on Agent construction |
| `def _create_manager_session(self, session_id: str, stored: dict, primary: list[str], secondary: list[str]) -> Any` | id, stored data, skill paths | New session | `session_manager.create_session` with model/skills/tools/limits/initial messages | Synchronous; raises on create failure; run via `to_thread` |
| `async def _switch_to_session(self, session_id: str) -> None` | id | `None` | set active + state → off-thread save old (snapshot) → off-thread `_collect_summaries` → `_apply_summaries` → emit → off-thread load → hydrate if needed; stale-guards after each await | Emits `active_session_changed`; blocking I/O off the GUI thread |
| `def _auto_select_session(self) -> None` | — | `None` | latest id → emit `session_switch_started` + switch, else create timestamp session → emit + refresh | Emits `session_switch_started`/`active_session_changed` |
| `def _delete_session_by_id(self, session_id: str) -> None` | id | `None` | cancel pending → remove manager/store → reselect (emit `session_switch_started`) → refresh/switch | Emits `session_switch_started`/`active_session_changed` |
| `def _cancel_pending_operations(self, state: SessionState, session_id: str) -> None` | state, id | `None` | deny pending tool → set `approval_event` → cancel `active_task` | Schedules `deny_tool`; cancels task |
| `def _spawn(self, coro: Coroutine) -> None` | coroutine | `None` | `asyncio.ensure_future` → track in `_tasks` → discard on done | Fire-and-forget task |
| `def _emit_validation_issues(self) -> None` | — | `None` | read `skill_manager.get_validation_issues()` → group warnings/errors → toast | Emits `toast_requested` |
