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
- `panelCount` / `maxPanels` / `panelOrder` / `panelAt(slot)` — the workspace
  panels for `SplitWorkspace.qml`. Panels live in a fixed set of slots
  (`MAX_PANELS = 4`); `panelOrder` lists the occupied slots in visual order and
  `panelAt(slot)` returns that slot's `ChatPanelModel`.
- `activeSessionName` — the selected session.
- `modelNames` — configured LLM model names for the per-chat model selector.
- `state()` registry of `ChatState` objects, one per chat.
- Session slots: create/switch/delete session, plus `open_session(name)` used by
  secondary windows (activates unconditionally via `_activate_session`) and
  `ensure_chat(slot)` to seed a newly created session with one chat.
- Chat slots: new chat in panel, activate tab, move, split, delete.
- Model slots: `modelNameFor(chat_id)`, `_handle_model_changed(chat_id, name)`.
- Layout engine: `_reconcile_panels`, `_sync_panels`, `_rebuild_changed_panels`,
  the transcript LRU (`_touch_transcript` / `_evict_transcripts`), background
  transcript pre-warming (`_prewarm_transcripts` / `_prewarm_sequence`), and the
  debounced off-thread `_save_layout` (with `_flush_layout_loop` /
  `flush_layout`).
- Persistence (`_create_stored_chat`, `_build_context_snapshot`) and hydration
  (`_hydrate_chat`, `_create_manager_chat`). Live-chat persistence is owned by
  the [`chat-worker`](chat-worker.md), not this controller.
- Index-backed enrichment (`_collect_summaries` / `_apply_summaries`) with an
  off-thread `refresh_model_async` variant; reads `storage/chat_index.json`
  instead of parsing every chat file.
- `prewarm_enabled` — primary windows pre-warm transcripts; secondary windows set
  it to `False` to avoid duplicating workers and models.
- Cross-window sync: subscribes to [`SessionBus.sessions_changed`](qt-session-bus.md)
  via the `refresh_sessions` slot; emits the bus after in-app create/delete.

## Signals

| Signal | Payload | Meaning |
|---|---|---|
| `sessions_changed` | — | Session list/menu changed (notifies `sessionMenuModel`) |
| `tabs_changed` | — | Panel tab rows changed |
| `panels_changed` | — | Panel layout changed (notifies `panelCount` / `panelOrder`) |
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
| `maxPanels` | `int` | constant | Fixed slot count backing the QML panel repeater (`MAX_PANELS = 4`) |
| `panelOrder` | `list[int]` | `panels_changed` | Occupied panel slots in left-to-right visual order |
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
   `_open_session_panels()` → `_prewarm_transcripts()`.

### Layout reconcile (`_reconcile_panels`)

1. Read the stored layout (`chat_store.get_layout`); take at most 4 splits.
2. Keep only chat ids that exist in the session; chats missing from the layout
   are appended to the first panel.
3. Drop empty panels (always keep one) and persist via `_save_layout`.

### Panel sync (`_sync_panels`)

1. Ensure at least one panel exists.
2. Touch every panel's active chat in the transcript LRU and evict the oldest
   non-active chats above the `MAX_PANELS * 2` limit, releasing their runtime.
   Active chats are never evicted.
3. For each panel, set the model of its **fixed slot** active chat, `ChatModel`,
   and tab rows (enriched chats in layout order), the active+warm transcript ids,
   plus runtime values from `_panel_runtime`.
   Slots not occupied by a panel are cleared. Because a slot that keeps the same
   chat is a compare-and-emit no-op, panels that merely shift position emit
   nothing and QML never rebuilds their delegate. `ChatTabModel.set_chats` and
   `TranscriptListModel.set_ids` merge incrementally as well.
4. `chat.set_visible_chats(...)` so the chat controller only paints visible
   chats; emit `panels_changed` and `tabs_changed`.

### New chat (`_handle_new_chat(slot)`)

Capture the panel's current active chat as the inheritance source → unique id →
`_create_stored_chat(chat_id, source_chat_id)` (copies the source's
`skills_config` and `model_name`; empty config / config-default model when there
is no source) → append to that panel's tabs + set active → refresh/save →
`_open_chat`.

### Split / move (`_handle_split`, `_handle_move_chat`)

- **Split** (`chat_id, target_slot, "left"|"right"`): remove the chat from its
  panel(s), keep the target panel even if emptied, and insert a new panel with
  the chat adjacent to it. The new panel gets the lowest free slot (max
  `MAX_PANELS = 4`; at the limit the drop hint is suppressed in QML and the slot
  early-returns).
- **Move** (`chat_id, target_slot`): remove the chat, append it to the target
  panel's tabs and activate it; empty source panels collapse.

Because panels occupy **fixed slots**, adding/removing/moving one only changes
each delegate's `x`/`visibility`; a panel keeps its `ChatPanelModel` as it moves,
so untouched panels are never re-rendered. Both handlers snapshot the slot→active
map before mutating and call `_rebuild_changed_panels(old_active)` before
`_finalize_panel_change()`: only slots whose active chat actually changed have
their worker asked to re-render (`chat.rebuild_chat_display`). A cold model is
built in staged batches behind the loading overlay; a populated model is merged
in place. `_open_chat` then activates the moved chat.

### Transcript cache (`_touch_transcript` / `_evict_transcripts`)

Each window keeps at most `_TRANSCRIPT_CACHE_LIMIT = MAX_PANELS * 2` chats with a
live Python render model. QML materializes only each panel's active chat plus one
warm transcript (`_panel_transcript_ids`), so hidden tabs keep their rendered
`ChatListModel` rows but no card delegates. `_open_chat` and `_sync_panels` touch
the active chats. When the cache is over the limit, `_evict_transcripts` drops the
non-active chat with the oldest `updated_at` (the access-order LRU is only a
tie-breaker) and calls `ChatController.release_chat`, which stops the worker,
removes the agent, and clears the rendered model. `_forget_chat` removes a deleted
chat, and `_activate_session` cancels in-flight pre-warms and clears the LRU so the
previous session's views are released.

### Transcript pre-warm (`_prewarm_transcripts` / `_prewarm_sequence`)

Called at primary-window start (`start`) and on every session activation
(`_activate_session`, used by both `open_session` and `_handle_switch_session`).
Secondary windows set `prewarm_enabled = False`, so they never pre-warm. It builds
the priority list:

1. every panel's active chat (visible immediately), in panel order;
2. the remaining session chats with messages, sorted by `updated_at` descending.

The list is capped at `len(active) + _PREWARM_AHEAD` (2), bounded by
`_TRANSCRIPT_CACHE_LIMIT = MAX_PANELS * 2`. Active chats are already seeded by
`_open_chat`; `_prewarm_sequence` adds each remaining chat to the LRU one at a
time, evicts the oldest-updated non-active chat when over the limit, pushes the
updated transcript ids to the panels via `_sync_transcript_models`, and renders
the chat via `ChatController.prewarm_chat`. The render itself runs on the chat's
own worker thread (no process pool), and the sequence yields for
`_PREWARM_GAP = 0.25 s` between chats so the GUI stays responsive. Adding
transcripts one at a time avoids instantiating all cached views in a single burst
on a session switch. A per-window `_prewarm_generation` stops an older sequence
when the session changes again.

`_activate_session` also calls `ChatController.release_all_chats()` before
rebuilding, which releases idle old-session workers/agents/models without blocking
the GUI (busy chats keep running). `_switching_session` suppresses the redundant
`_sync_panels` inside `_apply_summaries` so the old panel set is not rebuilt just
before it is replaced.

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
3. Read `skills_config.activated`, canonicalise each path with
   `skill_manager.normalize_skill_path`; create the live chat through
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
| `def build(self) -> None` | — | `None` | create menu model + panel lists → install `ChatController.model_for` provider → init `_transcript_lru`/`_states`/`_tasks` → `_refresh_model()` → connect `SessionBus.sessions_changed` → `refresh_sessions` | Emits `sessions_changed`; subscribes to the bus |
| `@Slot() def refresh_sessions(self) -> None` | — | `None` | off-thread `refresh_model_async` (`_spawn`) | Cross-window slot connected to `SessionBus.sessions_changed` |
| `@Property(int, notify=panels_changed) def panelCount(self) -> int` | — | Panel count | `len(self._panels)` | — |
| `@Property(int, constant=True) def maxPanels(self) -> int` | — | Slot count | `MAX_PANELS` | Fixed QML repeater size |
| `@Property(list, notify=panels_changed) def panelOrder(self) -> list[int]` | — | Occupied slots | `[panel["slot"] for panel in _panels]` | Visual left-to-right order for QML |
| `@Slot(int, result=QObject) def panelAt(self, slot: int) -> QObject` | `slot` | `ChatPanelModel` | `_panel_models[slot]` (clamped to 0) | Slots created once in `build()` |
| `@Property(QObject, notify=sessions_changed) def sessionMenuModel(self)` | — | `SessionMenuModel` | returns `_session_menu_model` | — |
| `@Property(str, notify=active_session_name_changed) def activeSessionName(self) -> str` | — | Active session name | `active_session_name or ""` | — |
| `def state(self, chat_id: str) -> ChatState` | `chat_id` | The chat's state | create-on-demand into `_states` | Inserts a new `ChatState` |
| `@Slot() def start(self) -> None` | — | `None` | ensure Default → refresh → reconcile → sync → open panels → prewarm transcripts | Toasts; emits activation |
| `@Slot(int) def _handle_new_chat(self, slot: int)` | panel slot | `None` | capture source chat → unique id → store (inheriting config/model) → append tab → refresh/save → open | Writes store; emits signals |
| `@Slot(int, str) def _handle_panel_activate(self, slot, chat_id)` | panel slot, chat | `None` | set panel active → save → sync → open | Emits activation |
| `@Slot(str, int) def _handle_move_chat(self, chat_id, target_slot)` | chat, panel slot | `None` | snapshot actives → remove chat → append to target → `_rebuild_changed_panels` → finalize → open | Mutates layout; saves |
| `@Slot(str, int, str) def _handle_split(self, chat_id, target_slot, side)` | chat, panel slot, `"left"`/`"right"` | `None` | snapshot actives → remove chat → insert new panel adjacent to target → `_rebuild_changed_panels` → finalize → open | Max `MAX_PANELS`; saves |
| `@Slot(str) def _handle_delete_chat(self, chat_id)` | chat | `None` | `_delete_chat_by_id` | Deletes store + panel tab |
| `@Slot() def _handle_new_session(self)` | — | `None` | emit `new_session_requested` | QML opens dialog |
| `@Slot(str) def _handle_create_session(self, name)` | name | `None` | strip → create session → switch → emit bus | `ValueError` → toast; emits `SessionBus.sessions_changed` |
| `@Slot(str) def _handle_switch_session(self, name)` | name | `None` | no-op if already active → `_activate_session` | Rebuilds all panels |
| `@Slot(str) def open_session(self, name)` | name | `None` | `_activate_session` (no skip) | Used by new windows |
| `@Slot(int) def ensure_chat(self, slot=0)` | panel slot | `None` | `_handle_new_chat` when the session has no chats | Seeds a fresh session with one chat |
| `def _activate_session(self, name)` | name | `None` | set active → emit → cancel pre-warms → release idle old chats → clear transcript LRU → refresh (no panel sync) → reconcile → sync → open → prewarm | Shared by switch/open |
| `@Slot(str) def _handle_delete_session(self, name)` | name | `None` | delete session + chats → forget → fallback Default → rebuild → emit bus | `ValueError` → toast; emits `SessionBus.sessions_changed` |
| `@Slot(str, result=str) def statusColor(self, status)` | status | Hex color | `_STATUS_COLORS.get(status, COLOR_CHAT_EMPTY)` | — |
| `@Slot(str, result=str) def modelNameFor(self, chat_id)` | chat | Model name | `state.model_name` or the config default (in-memory) | May create a `ChatState` |
| `@Slot(str, str) def _handle_model_changed(self, chat_id, model_name)` | chat, model | `None` | validate against `llm_models` → set `state.model_name` → persist → `Agent.set_model` if live → refresh panel | Writes store; toasts on unknown model |
| `@Slot(str) def refresh_chat_panels(self, chat_id)` | chat | `None` | derive live status/blink → push `update_tab` to every panel owning the chat → `set_runtime` for the panel showing it | Updates `ChatPanelModel`/`ChatTabModel`; runs on every `chat_state_changed` |
| `@Slot(str) def refresh_chat_tokens(self, chat_id)` | chat | `None` | read true counts from `ChatState` → `set_tokens` on the panel showing the chat | Updates `ChatPanelModel` only; runs on every `chat_tokens_changed` |
| `def _chat_display_status(self, chat_id)` | chat | `ChatStatus` | live `ChatState.message_count` (fallback enriched summary) → `_status_from_state` | Disk-free; GUI thread only |
| `@staticmethod def _status_from_state(state, has_messages)` | state; message presence | `ChatStatus` | busy → `WAITING`/`RUNNING`; error → `ERROR`; else `FINISHED`/`EMPTY` | Pure |
| `def _reconcile_panels(self, name)` | session | `None` | stored layout vs session chats → slot-tagged `_panels` | Saves layout |
| `def _sync_panels(self)` | — | `None` | touch active chats in the transcript LRU → evict above `MAX_PANELS * 2` (releasing runtime) → push each panel's slot data, active+warm transcript ids, and runtime into `ChatPanelModel`s; clear unused slots; set visible chats | Emits `panels_changed`/`tabs_changed` |
| `@staticmethod def _new_panel(slot, chat_ids=None, active_chat_id="")` | slot, tabs, active | Panel dict | `{"slot", "chat_ids", "active_chat_id"}` | Pure |
| `def _allocate_slot(self)` | — | `int` | lowest slot not currently in use | Returns `0` when full |
| `def _panel_by_slot(self, slot)` | slot | Panel dict or `None` | linear search of `_panels` | — |
| `def _active_by_slot(self)` | — | `dict[int, str]` | snapshot of slot → active chat | Used before layout mutation |
| `def _rebuild_changed_panels(self, old_active)` | old slot→active map | `None` | background rebuild only slots whose active chat changed | Calls `chat.rebuild_chat_display`; populated models are merged, cold ones staged |
| `def _touch_transcript(self, chat_id)` | chat | `None` | move the chat to the MRU end of `_transcript_lru` | — |
| `def _chat_updated_at(self, chat_id)` | chat | `updated_at` string | read from `_enriched` | `""` when unknown |
| `def mark_chat_updated(self, chat_id)` | chat | `None` | stamp `_enriched[chat_id]["updated_at"]` with the current time | Keeps transcript eviction order current after a turn |
| `def _evict_transcripts(self)` | — | `None` | drop the non-active chat with the oldest `updated_at` above `_TRANSCRIPT_CACHE_LIMIT = MAX_PANELS * 2` | Active chats are never evicted; calls `ChatController.release_chat` |
| `def _prewarm_transcripts(self)` | — | `None` | build active-first / newest-updated priority list, sync active transcripts, spawn sequence | Capped at `len(active) + _PREWARM_AHEAD`; disabled on secondary windows |
| `def _panel_transcript_ids(self, panel)` | panel | list[str] | active chat + one recently touched warm chat | Keeps QML delegates bounded per panel |
| `def _sync_transcript_models(self)` | — | `None` | push each panel's active + warm chat ids into its `ChatPanelModel` | Lighter than `_sync_panels`; no layout signals |
| `async def _prewarm_sequence(self, ordered, active, generation)` | priority ids, active ids, generation | `None` | wait for active plans, then add + `ChatController.prewarm_chat` each remaining id | Stops when `_prewarm_generation` changes |
| `def _panel_runtime(self, chat_id)` | chat | 11-tuple | busy/approval/tokens/loading + activated/allow/ask/block counts + model name | Reads `ChatState`; tokens are the true `token_usage` values (no estimate) |
| `def _save_layout(self)` | — | `None` | snapshot `{splits:[{chat_ids, active_chat_id}]}` and queue a debounced off-thread persist | No synchronous disk I/O; collapses rapid calls |
| `async def _flush_layout_loop(self)` | — | `None` | wait `_LAYOUT_SAVE_DEBOUNCE`, then `to_thread(chat_store.set_layout)` for the newest pending layout | Worker-thread disk write |
| `def flush_layout(self)` | — | `None` | synchronously persist any pending layout (app shutdown) | GUI-thread disk write |
| `def _open_chat(self, chat_id)` | chat | `None` | set active → touch transcript LRU → evict → sync transcript models → emit `chat_switch_started` → spawn `_open_chat_async` | Emits signals; ensures a moved/activated chat gets its transcript |
| `async def _open_chat_async(self, chat_id)` | chat | `None` | skip load if already hydrated → off-thread load → hydrate if needed → emit `active_chat_changed` | Hydration may toast |
| `def _open_session_panels(self)` | — | `None` | `_open_chat` each panel's active chat | Emits signals |
| `def open_chat_after(self, source_chat_id, new_chat_id)` | source chat, new chat | `None` | append new chat to source's panel → refresh/save/open | Used by compaction |
| `def _remove_chat_from_panels(self, chat_id)` | chat | `None` | remove from every panel; drop empties | Caller ensures ≥1 panel |
| `def _delete_chat_by_id(self, chat_id)` | chat | `None` | forget → store delete → remove from panels → `_rebuild_changed_panels` → refresh → reopen if active | Deletes store |
| `def _forget_chat(self, chat_id)` | chat | `None` | pop state, pop transcript LRU, `chat.forget_chat`, cancel pending, remove live agent | Cancels task |
| `def _refresh_model(self)` | — | `None` | `_collect_summaries()` → `_apply_summaries()` | Emits `sessions_changed` |
| `async def refresh_model_async(self)` | — | `None` | snapshot `_states` → off-thread `load_summaries`/`_enrich_chat`/`list_sessions` → `_apply_summaries` on GUI thread | Uses the on-disk chat index; no full chat parse |
| `def _collect_summaries(self) -> tuple[list[dict], list[str]]` | — | `(enriched, sessions)` | snapshot `_states` → `load_summaries()` (index rows) → `_enrich_chat` → `list_sessions()` | Thread-safe |
| `def _apply_summaries(self, enriched, sessions)` | summaries; session names | `None` | seed chat counts + model name + persisted true token counts → group by session → set menu model → emit → `_sync_panels` unless `_switching_session` | GUI thread only |
| `def _enrich_chat(self, stored, states) -> dict` | summary row; states snapshot | Summary + `title`/`status`/`model_name` + counts + `true_input_tokens`/`true_output_cum` | use index fields, fall back to deriving from a full dict | No extra disk read |
| `@staticmethod def _derive_chat_title(sess) -> str` | stored chat | Title | first user message (30 chars) else id[:15] | Handles multimodal content lists |
| `def _derive_chat_status(self, cid, stored, states) -> str` | id, stored, states | `ChatStatus` | `has_messages` from summary or stored messages → `_status_from_state` | — |
| `@staticmethod def _build_context_snapshot(chat) -> dict` | live chat | Snapshot | `sys_prompt`, `_pending_sys_message`, skills, `_tools`, `_tool_config` | — |
| `def _create_stored_chat(self, chat_id, source_chat_id="")` | id; optional source chat | `None` | new record with `session`/`messages`/`true_input_tokens`/`true_output_cum`; `skills_config`/`model_name` copied from `source_chat_id` else empty config / config default → save | Writes store |
| `def _chat_save_snapshot(self, chat_id)` | id | `(messages, snapshot)` or `None` | capture live messages/context on the GUI thread | — |
| `def _save_current_chat_for(self, chat_id, snapshot=None)` | id; optional snapshot | `None` | legacy helper; live-chat persistence now runs on the worker (`ChatWorker._do_persist`) | Writes store |
| `def _generate_unique_chat_id(self) -> str` | — | Unique id | timestamp base, suffixed while colliding | — |
| `async def _hydrate_chat(self, chat_id, stored=None)` | id; optional stored | Live chat or `None` | existing → off-thread load → off-thread `_create_manager_chat` → `refresh_estimated` → restore persisted token counts → snapshot save | `ChatError` path logs + toasts |
| `def _create_manager_chat(self, chat_id, stored, activated)` | id, stored, skill paths | New chat | normalize `activated` paths → resolve `stored.model_name` (fallback default) → `chat_manager.create_chat` with model/skills/tools/`chat_limits`/initial messages | Synchronous; run via `to_thread` |
| `def _cancel_pending_operations(self, chat_id)` | id | `None` | `remove_worker(chat_id)` + `chat_manager.remove_chat` | Stops the chat's worker thread |
| `def _spawn(self, coro)` | coroutine | `None` | `asyncio.ensure_future` → track → discard on done | Fire-and-forget |
| `def _emit_validation_issues(self)` | — | `None` | group warnings/errors from `skill_manager` → toast | Emits `toast_requested` |
