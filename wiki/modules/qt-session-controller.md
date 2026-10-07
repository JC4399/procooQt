# qt.session_controller — sessions & split workspace

Source: `src/qt/session_controller.py`

## Purpose

Owns the **session** list (the title-bar menu), the **split-workspace layout**
(1–4 panels), the `ChatTabModel` per panel, and the per-chat
[`ChatState`](qt-chat-state.md) registry. Implements session creation,
switching, deletion, the `Default` session, chat create/switch/delete, panel
split/move, persistence, and hydration. Every panel exposes a
[`ChatPanelModel`](qt-chat-panel-model.md) to QML. Each controller subscribes to
the shared [`SessionBus`](qt-session-bus.md) so a session created or deleted in
any window refreshes every window's title-bar list.

## Deliverables

- `ChatStatus` string constants and the `_STATUS_COLORS` lookup.
- `sessionMenuModel` (`SessionMenuModel`) — sessions + trailing `+` for
  `SessionSelector.qml`.
- `panelCount` / `panelAt(index)` — the workspace panels for
  `SplitWorkspace.qml`; each panel is a `ChatPanelModel`.
- `activeSessionName` — the selected session.
- `modelNames` — configured LLM model names for the per-chat model selector.
- `state()` registry of `ChatState` objects, one per chat.
- Session slots: create/switch/delete session, plus `open_session(name)` used by
  secondary windows (activates unconditionally via `_activate_session`) and
  `ensure_chat(panel_index)` to seed a newly created session with one chat.
- Chat slots: new chat in panel, activate tab, move, split, delete.
- Model slots: `modelNameFor(chat_id)`, `_handle_model_changed(chat_id, name)`.
- Layout engine: `_reconcile_panels`, `_sync_panels`, `_save_layout`.
- Persistence (`_create_stored_chat`, `_save_current_chat_for`,
  `_chat_save_snapshot`, `_build_context_snapshot`) and hydration
  (`_hydrate_chat`, `_create_manager_chat`).
- Single-pass enrichment (`_collect_summaries` / `_apply_summaries`) with an
  off-thread `refresh_model_async` variant.
- Cross-window sync: subscribes to [`SessionBus.sessions_changed`](qt-session-bus.md)
  via the `refresh_sessions` slot; emits the bus after in-app create/delete.

## Signals

| Signal | Payload | Meaning |
|---|---|---|
| `sessions_changed` | — | Session list/menu changed (notifies `sessionMenuModel`) |
| `tabs_changed` | — | Panel tab rows changed |
| `panels_changed` | — | Number of workspace panels changed (notifies `panelCount`) |
| `active_chat_changed` | `str` | A panel activated a chat id, or `""` when none |
| `active_session_name_changed` | — | Selected session changed |
| `chat_switch_started` | `str` | A chat switch was requested — emitted **before** hydration so the loading overlay can paint |
| `toast_requested` | `str, str` | Message + toast level (`TOAST_ERROR` / `TOAST_WARNING`) |
| `new_session_requested` | — | Ask QML to open the new-session dialog |
| `models_changed` | — | Notifies the `modelNames` property |

## Properties

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `panelCount` | `int` | `panels_changed` | Number of visible panels |
| `sessionMenuModel` | `SessionMenuModel` | `sessions_changed` | Session rows for the title-bar selector |
| `activeSessionName` | `str` | `active_session_name_changed` | Active session name (or `""`) |
| `modelNames` | `list` | `models_changed` | Configured LLM model names (model selector) |

## `ChatStatus`

| Status | Meaning |
|---|---|
| `EMPTY` | No stored messages |
| `RUNNING` | Busy with a generation |
| `WAITING` | Busy, awaiting tool approval |
| `FINISHED` | Has messages, idle |
| `ERROR` | Last generation errored or was stopped by the user |

`statusColor(status)` maps a status string to the matching `COLOR_CHAT_*`
theme constant (default `COLOR_CHAT_EMPTY`); `ChatTabBar.qml` calls it to paint
each tab's dot. `_derive_chat_status` (off-thread enrichment) and
`_chat_display_status` (immediate, disk-free) share `_status_from_state`, which
maps a `ChatState` + message presence to `RUNNING`/`WAITING` (busy),
`ERROR` (idle with `has_error`), else `FINISHED`/`EMPTY`.

## Steps / Flow

### Start (`start`)

1. `_emit_validation_issues()` toasts skill problems.
2. `active_session_name = chat_store.ensure_default_session()` (creates
   `Default` when no sessions exist).
3. `_refresh_model()` → `_reconcile_panels(session)` → `_sync_panels()` →
   `_open_session_panels()`.

### Layout reconcile (`_reconcile_panels`)

1. Read the stored layout (`chat_store.get_layout`); take at most 4 splits.
2. Keep only chat ids that exist in the session; chats missing from the layout
   are appended to the first panel.
3. Drop empty panels (always keep one) and persist via `_save_layout`.

### Panel sync (`_sync_panels`)

1. Ensure the panel-model list matches `_panels`.
2. For each panel, set its active chat, `ChatModel`, and tab rows
   (enriched chats in layout order), plus runtime values from `_panel_runtime`.
3. `chat.set_visible_chats(...)` so the chat controller only paints visible
   chats; emit `panels_changed` and `tabs_changed`.

### New chat (`_handle_new_chat(panel_index)`)

Capture the panel's current active chat as the inheritance source → unique id →
`_create_stored_chat(chat_id, source_chat_id)` (copies the source's
`skills_config` and `model_name`; empty config / config-default model when there
is no source) → append to that panel's tabs + set active → refresh/save →
`_open_chat`.

### Split / move (`_handle_split`, `_handle_move_chat`)

- **Split** (`chat_id, target_index, "left"|"right"`): remove the chat from its
  panel(s), keep the target panel even if emptied, and insert a new panel with
  the chat adjacent to it (max 4; at the limit the drop hint is suppressed in
  QML and the slot early-returns).
- **Move** (`chat_id, target_index`): remove the chat, append it to the target
  panel's tabs and activate it; empty source panels collapse.

### Delete chat (`_delete_chat_by_id`)

Forget state (`_forget_chat`) → delete from `ChatStore` → remove from panels →
refresh; if the active chat was removed, open another panel's active chat.

### Delete session (`_handle_delete_session`)

`chat_store.delete_session` (deletes its chats) → `_forget_chat` each → if it
was active, fall back to `Default` and rebuild → emit
[`SessionBus.sessions_changed`](qt-session-bus.md) so every other window also
refreshes its title-bar list.

### Cross-window refresh (`refresh_sessions`)

`build()` connects [`SessionBus.sessions_changed`](qt-session-bus.md) to
`refresh_sessions`, which schedules `refresh_model_async` (off-thread disk scan)
for that window. `_handle_create_session` also emits the bus after creating a
session. This keeps the title-bar `SessionSelector.qml` list consistent across
every open window whenever a session is created or deleted anywhere.

### Hydration (`_hydrate_chat` → `_create_manager_chat`)

1. Return the live chat if `chat_manager` already has it.
2. Load the stored record off-thread (toast + `None` if missing).
3. Read `skills_config.primary` / `.secondary`; create the live chat through
   `_create_manager_chat` **on a worker thread** via `asyncio.to_thread`. It
   calls `chat_manager.create_chat` with model config, loaded skill contents,
   tool functions/config, `chat_limits`, and `initial_messages`.
4. On failure wrap in `ChatError` (log `detail`, toast `brief`).
5. `await chat.refresh_estimated()` (offloaded); backfill and save
   `context_snapshot` off-thread if absent.
6. Restore persisted `true_input_tokens` / `true_output_cum` onto the chat's
   `ChatState` when it has no live true counts yet, so the token bar shows the
   last known values after a restart.

### Open (`_open_chat` / `_open_chat_async`)

Set `active_chat_id`, emit `chat_switch_started`, then off-thread load +
hydrate (when needed) and emit `active_chat_changed`.

### Model selection (`_handle_model_changed`)

`SkillDock.qml` binds its model dropdown to `session.modelNames` and
`session.modelNameFor(chatId)`. Selecting a model calls
`_handle_model_changed(chat_id, name)`, which validates the name, writes it to
the chat's `ChatState` and stored record, swaps the live `Agent` model via
`Agent.set_model`, and refreshes the panel (the `ChatPanelModel.modelName`
surfaced by `ConfigTokenBar`). New chats store the config default; unmarked
chats fall back to it.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def build(self) -> None` | — | `None` | create menu model + panel lists → init `_states`/`_tasks` → `_refresh_model()` → connect `SessionBus.sessions_changed` → `refresh_sessions` | Emits `sessions_changed`; subscribes to the bus |
| `@Slot() def refresh_sessions(self) -> None` | — | `None` | off-thread `refresh_model_async` (`_spawn`) | Cross-window slot connected to `SessionBus.sessions_changed` |
| `@Property(int, notify=panels_changed) def panelCount(self) -> int` | — | Panel count | `len(self._panels)` | — |
| `@Slot(int, result=QObject) def panelAt(self, index: int) -> QObject` | `index` | `ChatPanelModel` | grows `_panel_models` and returns the one at `index` | May create a model |
| `@Property(QObject, notify=sessions_changed) def sessionMenuModel(self)` | — | `SessionMenuModel` | returns `_session_menu_model` | — |
| `@Property(str, notify=active_session_name_changed) def activeSessionName(self) -> str` | — | Active session name | `active_session_name or ""` | — |
| `def state(self, chat_id: str) -> ChatState` | `chat_id` | The chat's state | create-on-demand into `_states` | Inserts a new `ChatState` |
| `@Slot() def start(self) -> None` | — | `None` | ensure Default → refresh → reconcile → sync → open panels | Toasts; emits activation |
| `@Slot(int) def _handle_new_chat(self, panel_index: int)` | panel index | `None` | capture source chat → unique id → store (inheriting config/model) → append tab → refresh/save → open | Writes store; emits signals |
| `@Slot(int, str) def _handle_panel_activate(self, panel_index, chat_id)` | panel index, chat | `None` | set panel active → save → sync → open | Emits activation |
| `@Slot(str, int) def _handle_move_chat(self, chat_id, target_index)` | chat, panel | `None` | remove chat → append to target → finalize → open | Mutates layout; saves |
| `@Slot(str, int, str) def _handle_split(self, chat_id, target_index, side)` | chat, panel, `"left"`/`"right"` | `None` | remove chat → insert new panel adjacent to target → finalize → open | Max 4; saves |
| `@Slot(str) def _handle_delete_chat(self, chat_id)` | chat | `None` | `_delete_chat_by_id` | Deletes store + panel tab |
| `@Slot() def _handle_new_session(self)` | — | `None` | emit `new_session_requested` | QML opens dialog |
| `@Slot(str) def _handle_create_session(self, name)` | name | `None` | strip → create session → switch → emit bus | `ValueError` → toast; emits `SessionBus.sessions_changed` |
| `@Slot(str) def _handle_switch_session(self, name)` | name | `None` | no-op if already active → `_activate_session` | Rebuilds all panels |
| `@Slot(str) def open_session(self, name)` | name | `None` | `_activate_session` (no skip) | Used by new windows |
| `@Slot(int) def ensure_chat(self, panel_index=0)` | panel | `None` | `_handle_new_chat` when the session has no chats | Seeds a fresh session with one chat |
| `def _activate_session(self, name)` | name | `None` | set active → emit → refresh → reconcile → sync → open | Shared by switch/open |
| `@Slot(str) def _handle_delete_session(self, name)` | name | `None` | delete session + chats → forget → fallback Default → rebuild → emit bus | `ValueError` → toast; emits `SessionBus.sessions_changed` |
| `@Slot(str, result=str) def statusColor(self, status)` | status | Hex color | `_STATUS_COLORS.get(status, COLOR_CHAT_EMPTY)` | — |
| `@Slot(str, result=str) def modelNameFor(self, chat_id)` | chat | Model name | `state.model_name` or the config default (in-memory) | May create a `ChatState` |
| `@Slot(str, str) def _handle_model_changed(self, chat_id, model_name)` | chat, model | `None` | validate against `llm_models` → set `state.model_name` → persist → `Agent.set_model` if live → refresh panel | Writes store; toasts on unknown model |
| `@Slot(str) def refresh_chat_panels(self, chat_id)` | chat | `None` | derive live status/blink → push `update_tab` to every panel owning the chat → `set_runtime` for the panel showing it | Updates `ChatPanelModel`/`ChatTabModel`; runs on every `chat_state_changed` |
| `@Slot(str) def refresh_chat_tokens(self, chat_id)` | chat | `None` | read true counts from `ChatState` → `set_tokens` on the panel showing the chat | Updates `ChatPanelModel` only; runs on every `chat_tokens_changed` |
| `def _chat_display_status(self, chat_id)` | chat | `ChatStatus` | live `ChatState` + live agent messages (fallback enriched summary) → `_status_from_state` | Disk-free; GUI thread only |
| `@staticmethod def _status_from_state(state, has_messages)` | state; message presence | `ChatStatus` | busy → `WAITING`/`RUNNING`; error → `ERROR`; else `FINISHED`/`EMPTY` | Pure |
| `def _reconcile_panels(self, name)` | session | `None` | stored layout vs session chats → `_panels` | Saves layout |
| `def _sync_panels(self)` | — | `None` | push layout + runtime into `ChatPanelModel`s; set visible chats | Emits `panels_changed`/`tabs_changed` |
| `def _panel_runtime(self, chat_id)` | chat | 11-tuple | busy/approval/tokens/loading + primary/allow/ask/block counts + model name | Reads `ChatState`; tokens are the true `token_usage` values (no estimate) |
| `def _save_layout(self)` | — | `None` | write `{splits:[{chat_ids, active_chat_id}]}` to the store | Writes store |
| `def _open_chat(self, chat_id)` | chat | `None` | set active → emit `chat_switch_started` → spawn `_open_chat_async` | Emits signals |
| `async def _open_chat_async(self, chat_id)` | chat | `None` | off-thread load → hydrate if needed → emit `active_chat_changed` | Hydration may toast |
| `def _open_session_panels(self)` | — | `None` | `_open_chat` each panel's active chat | Emits signals |
| `def open_chat_after(self, source_chat_id, new_chat_id)` | source chat, new chat | `None` | append new chat to source's panel → refresh/save/open | Used by compaction |
| `def _remove_chat_from_panels(self, chat_id)` | chat | `None` | remove from every panel; drop empties | Caller ensures ≥1 panel |
| `def _delete_chat_by_id(self, chat_id)` | chat | `None` | forget → store delete → remove from panels → refresh → reopen if active | Deletes store |
| `def _forget_chat(self, chat_id)` | chat | `None` | pop state, cancel pending, remove live agent | Cancels task |
| `def _refresh_model(self)` | — | `None` | `_collect_summaries()` → `_apply_summaries()` | Emits `sessions_changed` |
| `async def refresh_model_async(self)` | — | `None` | snapshot `_states` → off-thread `load_all_chats`/`_enrich_chat`/`list_sessions` → `_apply_summaries` on GUI thread | Used by the chat controller's debounced streaming refresh |
| `def _collect_summaries(self) -> tuple[list[dict], list[str]]` | — | `(enriched, sessions)` | snapshot `_states` → `load_all_chats()` (one parse/file) → `_enrich_chat` → `list_sessions()` | Thread-safe |
| `def _apply_summaries(self, enriched, sessions)` | summaries; session names | `None` | seed chat counts + model name + persisted true token counts → group by session → set menu model → emit → `_sync_panels` | GUI thread only |
| `def _enrich_chat(self, stored, states) -> dict` | stored chat; states snapshot | Summary + `title`/`status`/`model_name` + counts + `true_input_tokens`/`true_output_cum` | derive title/status/counts/model/tokens from loaded data | No extra disk read |
| `@staticmethod def _derive_chat_title(sess) -> str` | stored chat | Title | first user message (30 chars) else id[:15] | — |
| `def _derive_chat_status(self, cid, stored, states) -> str` | id, stored, states | `ChatStatus` | `has_messages` from stored → `_status_from_state` | — |
| `@staticmethod def _build_context_snapshot(chat) -> dict` | live chat | Snapshot | `sys_prompt`, `_pending_sys_message`, skills, `_tools`, `_tool_config` | — |
| `def _create_stored_chat(self, chat_id, source_chat_id="")` | id; optional source chat | `None` | new record with `session`/`messages`/`true_input_tokens`/`true_output_cum`; `skills_config`/`model_name` copied from `source_chat_id` else empty config / config default → save | Writes store |
| `def _chat_save_snapshot(self, chat_id)` | id | `(messages, snapshot)` or `None` | capture live messages/context on the GUI thread | — |
| `def _save_current_chat_for(self, chat_id, snapshot=None)` | id; optional snapshot | `None` | replace `messages`/`message_count`/`context_snapshot` + persisted true token counts → `save_chat` (atomic) | Writes store |
| `def _generate_unique_chat_id(self) -> str` | — | Unique id | timestamp base, suffixed while colliding | — |
| `async def _hydrate_chat(self, chat_id, stored=None)` | id; optional stored | Live chat or `None` | existing → off-thread load → off-thread `_create_manager_chat` → `refresh_estimated` → restore persisted token counts → snapshot save | `ChatError` path logs + toasts |
| `def _create_manager_chat(self, chat_id, stored, primary, secondary)` | id, stored, skill paths | New chat | resolve `stored.model_name` (fallback default) → `chat_manager.create_chat` with model/skills/tools/`chat_limits`/initial messages | Synchronous; run via `to_thread` |
| `def _cancel_pending_operations(self, state, chat_id)` | state, id | `None` | deny pending tool → set `approval_event` → cancel `active_task` | Schedules `deny_tool` |
| `def _spawn(self, coro)` | coroutine | `None` | `asyncio.ensure_future` → track → discard on done | Fire-and-forget |
| `def _emit_validation_issues(self)` | — | `None` | group warnings/errors from `skill_manager` → toast | Emits `toast_requested` |
