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
  `_save_current_session_for`, `_build_context_snapshot`).
- Hydration helpers (`_hydrate_session`, `_create_manager_session`) and the
  switching/auto-select/delete flows.

## Signals

| Signal | Payload | Meaning |
|---|---|---|
| `sessions_changed` | — | Sidebar rows changed (also notifies `session_model`) |
| `active_session_changed` | `str` | Active session id, or `""` when none |
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
3. Prepend the id to `session_ids`; `_spawn(_switch_to_session(id))`.

### Switch (`_switch_to_session`)

1. Save the previous session via `_save_current_session_for(old_sid)`.
2. Set `active_session_id`; create/get its `SessionState`.
3. `_refresh_model()`; emit `active_session_changed` (chat + skill react).
4. If the session is not live but has stored messages, `await
   _hydrate_session(...)`.

### Delete (`_delete_session_by_id`)

1. Pop the `SessionState`; `_cancel_pending_operations` (deny tool, release
   approval, cancel task).
2. `session_manager.remove_session` + `session_store.delete_session`.
3. Remove from `session_ids`; if it was active, select the first remaining id or
   emit `active_session_changed("")`.
4. `_refresh_model()`; switch to the replacement when applicable.

### Hydration (`_hydrate_session` → `_create_manager_session`)

1. Return the live session if `session_manager` already has it.
2. Load the stored record (toast + `None` if missing).
3. Read `skills_config.primary` / `.secondary`; create the live session through
   `session_manager.create_session` with model config, loaded skill contents,
   tool functions/config, limits, and `initial_messages`.
4. On failure wrap in `SessionError` (log `detail`, toast `brief`).
5. `await session.refresh_estimated()`; backfill and save `context_snapshot` if
   absent.

### Auto-select (`_auto_select_session`)

- If sessions exist, switch to `session_ids[0]`.
- Otherwise create a timestamp session, mark it active, refresh, and emit
  `active_session_changed`.

### Folder operations

`_handle_create_folder` / `_handle_delete_folder` / `_handle_drop_on_folder`
delegate to `session_store`, map `ValueError` to an error toast, and call
`_refresh_model`. `_handle_folder_expansion` records expansion on the model and
refreshes; `is_folder_expanded` reads it back for QML.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def build(self) -> None` | — | `None` | create `SessionListModel` → init `_states`/`_tasks` → seed `session_ids` from store → `_refresh_model()` | Emits `sessions_changed` |
| `@Property(QObject, notify=sessions_changed) def session_model(self) -> SessionListModel` | — | The list model | returns `_session_model` | Notify signal is `sessions_changed` |
| `def state(self, session_id: str) -> SessionState` | `session_id` | The session's state | create-on-demand into `_states` | Inserts a new `SessionState` |
| `@Slot() def start(self) -> None` | — | `None` | `_emit_validation_issues()` → `_auto_select_session()` | Toasts; emits `active_session_changed` |
| `@Slot() def _handle_new_session(self) -> None` | — | `None` | unique id → `_create_stored_session` → prepend id → `_spawn(_switch_to_session)` | Writes store; switches |
| `@Slot(str) def _handle_session_click(self, session_id: str) -> None` | `session_id` | `None` | no-op on empty → `_spawn(_switch_to_session)` | Switches session |
| `@Slot(str) def _handle_delete_session(self, session_id: str) -> None` | `session_id` | `None` | no-op on empty → `_delete_session_by_id` | Deletes store + model rows |
| `@Slot() def _handle_new_folder(self) -> None` | — | `None` | emits `new_folder_requested` | QML opens the dialog |
| `@Slot(str) def _handle_create_folder(self, name: str) -> None` | `name` | `None` | strip → empty toast → `session_store.create_folder` → expand + refresh | `ValueError` → error toast |
| `@Slot(str) def _handle_delete_folder(self, name: str) -> None` | `name` | `None` | no-op on empty → `session_store.delete_folder` → refresh | `ValueError` → error toast |
| `@Slot(str, str) def _handle_drop_on_folder(self, session_id: str, folder: str) -> None` | `session_id`; `folder` (empty = unfiled) | `None` | `set_session_folder(id, folder or None)` → refresh | `ValueError` → error toast |
| `@Slot(str, bool) def _handle_folder_expansion(self, name: str, expanded: bool) -> None` | folder `name`, `expanded` | `None` | model `set_folder_expansion` → `_refresh_model` | Emits `sessions_changed` |
| `@Slot(str, result=bool) def is_folder_expanded(self, name: str) -> bool` | folder `name` | Expanded flag | model `is_expanded` | — |
| `@Slot(str, result=str) def statusColor(self, status: str) -> str` | status string | Hex color | `_STATUS_COLORS.get(status, COLOR_SESSION_EMPTY)` | — |
| `def _refresh_model(self) -> None` | — | `None` | list summaries → rebuild `session_ids` → enrich → list folders → `set_sessions(...)` → emit | Emits `sessions_changed` |
| `def _enrich_session(self, summary: dict) -> dict` | store summary | Summary + `title`/`status` | load stored → derive title/status | Loads each session from store |
| `@staticmethod def _derive_session_title(sess: dict) -> str` | stored session | Title | first user message, first 30 chars + `...`, else id[:15] | — |
| `def _derive_session_status(self, sid: str, stored: dict \| None) -> str` | id, stored data | `SessionStatus` | busy → `WAITING`/`RUNNING`; else `EMPTY`/`FINISHED` | Reads `_states` |
| `@staticmethod def _build_context_snapshot(session: Any) -> dict` | live session | Snapshot dict | grabs `sys_prompt`, `_pending_sys_message`, skills, `_tools`, `_tool_config` | — |
| `def _create_stored_session(self, session_id: str) -> None` | id | `None` | build empty record with `skills_config`/`messages`/timestamps → save | Writes store |
| `def _save_current_session_for(self, session_id: str) -> None` | id | `None` | live session → load stored → replace `messages`, `message_count`, `context_snapshot` → save | Writes store |
| `def _generate_unique_session_id(self) -> str` | — | Unique id | timestamp base, suffix while colliding with store/`session_ids` | — |
| `async def _hydrate_session(self, session_id: str, stored: dict \| None = None) -> Any` | id; optional stored data | Live session or `None` | existing → load → `_create_manager_session` → `refresh_estimated` → backfill snapshot | `SessionError` path logs + toasts |
| `async def _create_manager_session(self, session_id: str, stored: dict, primary: list[str], secondary: list[str]) -> Any` | id, stored data, skill paths | New session | `session_manager.create_session` with model/skills/tools/limits/initial messages | Raises on create failure |
| `async def _switch_to_session(self, session_id: str) -> None` | id | `None` | save old → set active + state → refresh → emit → hydrate if needed | Emits `active_session_changed` |
| `def _auto_select_session(self) -> None` | — | `None` | latest id → switch, else create timestamp session | Emits `active_session_changed` |
| `def _delete_session_by_id(self, session_id: str) -> None` | id | `None` | cancel pending → remove manager/store → reselect → refresh/switch | Emits `active_session_changed` |
| `def _cancel_pending_operations(self, state: SessionState, session_id: str) -> None` | state, id | `None` | deny pending tool → set `approval_event` → cancel `active_task` | Schedules `deny_tool`; cancels task |
| `def _spawn(self, coro: Coroutine) -> None` | coroutine | `None` | `asyncio.ensure_future` → track in `_tasks` → discard on done | Fire-and-forget task |
| `def _emit_validation_issues(self) -> None` | — | `None` | read `skill_manager.get_validation_issues()` → group warnings/errors → toast | Emits `toast_requested` |
