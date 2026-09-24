# qt.chat_controller — chat rendering, streaming & approval

Source: `src/qt/chat_controller.py`

## Purpose

Owns one [`ChatListModel`](#per-chat-model-cache) per chat and drives the ReAct
event loop for every live chat. Rendering is gated on a **visible-chat set** so
up to four split panels can stream independently. `chat.messages` stays
canonical: the render plan is derived from it, diffed by content hash, and
clipped into the model. Approval blocks the loop on an `asyncio.Event`, and long
streams are rendered with throttled in-place updates.

## Deliverables

- Per-chat `ChatListModel` cache; the active chat is exposed to a panel through
  [`ChatPanelModel`](qt-chat-panel-model.md), not directly.
- `set_visible_chats(ids)` — the set of chats currently shown in a panel.
- Per-chat action slots (`_handle_send_for`, `_handle_stop_for`,
  `_handle_regenerate_for`, `_handle_approve_for`, `_handle_deny_for`) plus
  focused-chat wrappers.
- The streaming generation loop split into hydrate / consume-events / cleanup
  phases.
- Incremental content-hash rendering (`_rebuild_chat_display` →
  `_compute_render_keys` → `_build_items` → `diff_update`), with the plan
  computed off the GUI thread for panel switches.
- The `_StagedBuildState` and `_RenderIndices` dataclasses.
- Tool approval via `asyncio.Event`, stop/regenerate, and automatic chat
  compaction.
- `chat_state_changed(chat_id)` — emitted whenever a chat's runtime state
  changes so `SessionController.refresh_chat_panels` can update its panel.

## Signals

| Signal | Payload | Meaning |
|---|---|---|
| `active_model_changed` | — | The focused `ChatListModel` changed |
| `approval_visibility_changed` | `bool` | Focused approval bar show/hide (legacy) |
| `token_counts_changed` | `int, int` | Focused input/output token counts (legacy) |
| `toast_requested` | `str, str` | Message + toast level |
| `busy_changed` | `bool` | Focused generation running state (legacy) |
| `loading_changed` | `bool` | Focused switch rebuild in progress (legacy) |
| `chat_state_changed` | `str` | A chat's runtime state changed (per-panel refresh) |

The `*_changed`/`busy`/`loading`/`activeModel`/tokens members are kept for the
focused chat; per-panel QML reads `ChatPanelModel` instead.

## Per-chat model cache

`_models: dict[str, ChatListModel]` holds one model per chat. `model_for(chat_id)`
creates on demand. `active_chat_id` is the last activated ("focused") chat;
`_visible_chat_ids` is the set of chats currently shown in any panel. Rendering
is applied only when `chat_id` is visible (`_is_visible`), while generation and
state tracking always run.

## Steps / Flow

### Send (`_handle_send_for(chat_id, text)`)

1. Reject empty text, missing chat, or a busy chat with an error toast.
2. `_append_user_message(chat_id, message)` — optimistic `append_item`.
3. `_launch_generation(chat_id, message)`.

`_handle_send(text)` forwards to `_handle_send_for(active_chat_id, text)`.

### Launch (`_launch_generation`)

1. Set `state.is_busy = True`; increment `state.generation_id` (`gen_id`).
2. `_append_waiting_placeholder(chat_id)` — the `w:pending` scanner renders in
   the same frame as the user card, before hydration.
3. `_refresh_sidebar()`; emit `chat_state_changed(chat_id)`.
4. `_spawn(_run_chat_loop(message, gen_id, chat_id))`.

### `_run_chat_loop` (phases)

1. **Hydrate** — `_hydrate_phase(chat_id, gen_id)` calls
   `session._hydrate_chat(...)`. On failure, clear busy/rebuild/refresh.
2. Start `task = asyncio.ensure_future(chat.run(message))`; store as
   `state.active_task`.
3. `await asyncio.sleep(0)`; rebuild the display when visible to reconcile the
   `u:<hash>` + `w:pending` keys.
4. **Consume** — `await _consume_events(chat, chat_id, state, task)`; then
   `await task` if pending. `asyncio.CancelledError` cancels the task.
5. **Cleanup** — `finally: _finalize_turn(...)` clears busy, rebuilds, resets
   the turn, saves the chat, refreshes, emits `chat_state_changed`.
6. If `chat.check_limit_exceeded() is not None`, run `_compact_chat`.

### Consume events (`_consume_events`)

Drains `chat.event_queue` while the task is pending or the queue is non-empty,
reading with `asyncio.wait_for(..., timeout=0.1)`. By `event["type"]`:

| Event type | Handling |
|---|---|
| `tool_call` (mode `ask`) | `await _handle_approval(chat_id, event, state)` — blocks |
| `tool_result` | Append to `state.tool_results` |
| `token_usage` | Set `true_input_tokens` / `true_output_cum`; emit `chat_state_changed` when visible |
| `done` | Break out of the loop |
| `error` | Toast the `brief` (when visible) and break |

After each event, a change in `len(chat.messages)` triggers `_refresh_sidebar()`,
and when visible `_render_active_event(...)` updates the display.

### Per-event rendering (`_render_active_event`)

- If the message count changed and the event is a `tool_result`, swap the
  pending result card in place via `_swap_pending_result_card(chat_id, ...)`.
- Otherwise rebuild the display.
- If unchanged and the last message is not an assistant message, rebuild; else
  `_update_live_assistant(chat_id, state)` (throttled).

### Rebuild pipeline

`_compute_render_plan(chat_id)` loads the state, stored snapshot, and a snapshot
of the live messages, then `_compute_render_keys` + `_build_items`. It returns
`(keys, items, snapshot, indices)` without mutating state, so it can run on a
worker thread.

`_rebuild_chat_display(chat_id)` applies the plan synchronously; after a panel
switch `_rebuild_chat_display_staged(chat_id)` builds it behind the loading
overlay, inserting `_RENDER_INSERT_BATCH` (8) rows per tick (clamped 6–20 ms
toward a 0.6 s target). The plan is computed off-thread.
`_skip_staged_build()` flushes the remainder before a user action;
`_cancel_staged_build()` drops it on a new activation.

### Live update throttling (`_update_live_assistant`)

- **Structural** changes force an immediate `_rebuild_chat_display`.
- A pending thinking/response card whose row does not exist yet rebuilds
  immediately.
- **Content-only** updates and streaming-tool-call argument changes are throttled
  to `_STREAM_UPDATE_INTERVAL` (0.08 s) and applied in place by
  `_apply_streaming_item_updates`.

### Approval (`_handle_approval`)

1. Create `state.approval_event`; set `pending_tool_info`, `approval_text`.
2. Refresh the sidebar; emit `chat_state_changed(chat_id)`; when visible, rebuild.
3. `await state.approval_event.wait()` — the loop is blocked here.
4. Clear pending/text; refresh; emit `chat_state_changed`.

`_approve(chat_id)`, `_deny(chat_id, reason)`, and `_stop_generation(chat_id)`
call `chat.approve_tool` / `chat.deny_tool` and `set()` the event.

### Stop / regenerate / approve / deny

- `_handle_stop_for(chat_id)` → `_stop_generation(chat_id)`.
- `_handle_regenerate_for(chat_id)` → `_regenerate(chat_id)`: find the last user
  message, trim the stored turn (`_trim_stored_chat`), drop delta banners, remove
  the live chat, rebuild, relaunch.
- `_handle_approve_for(chat_id)` → `_approve`; `_handle_deny_for(chat_id, reason)`
  → `_deny`.

### Compaction

`_compact_chat(chat_id, chat)` checks `chat.check_limit_exceeded()`; toasts when
visible, `await chat.summarize()`, and on success calls `_create_compacted_chat`.
That generates a new id, copies `skills_config`, `session`, `model_name`, and
`context_snapshot`, seeds `messages` with the summary, records `summary_of`, and
`session.open_chat_after(chat_id, new_id)`.

### Token accounting

`_update_token_bar(chat_id, state)` prefers true API counts when
`state.true_input_tokens > 0`, else the live chat's `_estimated_total` with zero
output. `ChatPanelModel` reads these through `SessionController._panel_runtime`;
`_set_token_counts` still emits `token_counts_changed` for the focused chat.
`_accumulate_tokens` counts only the appended suffix of each text field.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def build(self) -> None` | — | `None` | reset `_models`, `_visible_chat_ids`, `active_chat_id` | — |
| `def set_visible_chats(self, chat_ids: set[str]) -> None` | visible chat ids | `None` | store `_visible_chat_ids` | Gates rendering |
| `def _is_visible(self, chat_id: str) -> bool` | chat id | Bool | `chat_id in _visible_chat_ids` | — |
| `@Property(QObject, notify=active_model_changed) def activeModel(self)` | — | Focused model or `None` | `_models.get(active_chat_id)` | Legacy |
| `def model_for(self, chat_id: str) -> ChatListModel` | chat id | Chat model | create on demand | Inserts into `_models` |
| `def _refresh_sidebar(self) -> None` | — | `None` | `self.session._refresh_model()` | Emits `sessions_changed` |
| `def _spawn(self, coro: Coroutine) -> None` | coroutine | `None` | `ensure_future` → track → discard | Fire-and-forget |
| `@Slot(str, str) def _handle_send_for(self, chat_id, text)` | chat, text | `None` | validate → append → launch | Error toasts |
| `@Slot(str) def _handle_send(self, text)` | text | `None` | `_handle_send_for(active_chat_id, text)` | — |
| `@Slot(str) def _handle_stop_for(self, chat_id)` | chat | `None` | `_spawn(_stop_generation(chat_id))` | — |
| `@Slot(str) def _handle_regenerate_for(self, chat_id)` | chat | `None` | `_spawn(_regenerate(chat_id))` | — |
| `@Slot(str) def _handle_approve_for(self, chat_id)` | chat | `None` | `_spawn(_approve(chat_id))` | — |
| `@Slot(str, str) def _handle_deny_for(self, chat_id, reason)` | chat, reason | `None` | `_spawn(_deny(chat_id, reason))` | — |
| `@Slot(str) def _handle_chat_switch_started(self, chat_id)` | chat | `None` | `_cancel_staged_build()` → `_set_loading(chat_id, True)` | Shows the overlay at the user action |
| `@Slot(str) def _handle_chat_activated(self, chat_id)` | chat (may be `""`) | `None` | set focused id → clear caches → emit → `_set_loading(chat_id, True)` → `_spawn(_rebuild_after_switch)` | Emits `active_model_changed` |
| `async def _rebuild_after_switch(self, chat_id)` | chat | `None` | sleep(0) → visible check → staged rebuild → `_set_loading(chat_id, False)` → emit `chat_state_changed` | — |
| `def _launch_generation(self, chat_id, message)` | chat, text | `None` | busy + bump `generation_id` → append scanner → refresh → emit state → spawn loop | Mutates state |
| `async def _run_chat_loop(self, message, gen_id, chat_id)` | message, generation, chat | `None` | hydrate → run → reconcile → consume → finalize → compact on limit | Cancellable; persists |
| `async def _hydrate_phase(self, chat_id, gen_id)` | chat, generation | Live chat or `None` | `_hydrate_chat`; on failure clear busy/rebuild | Side effects on failure |
| `async def _consume_events(self, chat, chat_id, state, task)` | live chat, id, state, task | `None` | 0.1s poll → per-type branches | May block on approval |
| `def _render_active_event(self, event, chat, chat_id, state, msg_count, last_rendered)` | event + render context | New count | swap result vs rebuild vs live | May mutate model |
| `def _finalize_turn(self, chat_id, state, gen_id)` | chat, state, generation | `None` | clear busy → rebuild → reset → save → refresh → emit state | Persists |
| `async def _stop_generation(self, chat_id)` | chat | `None` | deny pending → set event → cancel task | Cancels task |
| `async def _approve(self, chat_id)` | chat | `None` | `approve_tool` → set event → emit state | Releases approval |
| `async def _deny(self, chat_id, reason)` | chat, reason | `None` | `deny_tool` → set event → emit state | Releases approval |
| `async def _regenerate(self, chat_id)` | chat | `None` | find last user → trim → drop deltas → remove live → rebuild → `_launch_generation` | Error toasts |
| `def _find_last_user_message(self, chat_id)` | chat | Last user text | live → stored messages | — |
| `def _trim_stored_chat(self, chat_id)` | chat | `None` | pop trailing non-user then user → save | Writes store |
| `async def _handle_approval(self, chat_id, event, state)` | chat, tool_call event, state | `None` | set event/pending → emit → await → clear | Blocks loop |
| `def _set_approval_visible(self, visible: bool)` | visibility | `None` | dedupe → store → emit | Focused bar |
| `async def _compact_chat(self, chat_id, chat)` | chat, live agent | `None` | limit check → toast → summarize → `_create_compacted_chat` | Toasts |
| `async def _create_compacted_chat(self, chat_id, summary)` | old id, summary | `None` | new record seeded with summary → `session.open_chat_after` | Writes store |
| `@Slot(str) def rebuild_chat_display(self, chat_id)` | chat | `None` | no-op on empty → `_rebuild_chat_display` | Public entry for skill sync |
| `def _compute_render_plan(self, chat_id)` | chat | `(keys, items, snapshot, indices)` | load stored → snapshot live/stored → keys + items | Pure; worker-thread safe |
| `def _apply_render_indices(self, state, indices)` | state, indices | `None` | copy row indices onto state | GUI thread only |
| `def _rebuild_chat_display(self, chat_id)` | chat | `None` | skip staged → plan → indices → `diff_update` → keys → tokens | Mutates model/state |
| `async def _rebuild_chat_display_staged(self, chat_id)` | chat | `None` | off-thread plan → indices → `_StagedBuildState` → batched inserts | Aborts on cancel/visibility change |
| `def _skip_staged_build(self)` / `def _cancel_staged_build(self)` | — | `None` | flush / drop the staged build | — |
| `def _compute_render_keys(self, state, messages, snapshot)` | state, messages, snapshot | Keys | banners → user/assistant/tool → trailing `w:pending` | — |
| `def _build_items(self, state, messages, snapshot)` | state, messages, snapshot | `(items, indices)` | banners → builders → waiting item | No state mutation |
| `def _append_user_message(self, chat_id, text)` | chat, text | `None` | `append_item(user item, key)` | Inserts a row |
| `def _append_waiting_placeholder(self, chat_id)` | chat | `None` | `append_item(waiting item, "w:pending")` | Inserts scanner |
| `def _swap_pending_result_card(self, chat_id, tool_call_id, tool_name, content)` | chat, tool call, content | `None` | find pending row → replace; else rebuild | Replaces a row |
| `def _update_live_assistant(self, chat_id, state)` | chat, state | `None` | structural rebuild vs throttled body update | Mutates model/state |
| `def _apply_streaming_item_updates(self, chat_id, state, ...)` | chat, state, texts, flags | `None` | accumulate tokens → `update_item` | Updates rows/state |
| `def _track_rendered_state(self, chat_id, state)` | chat, state | `None` | snapshot last assistant text/counts | Mutates state |
| `def _update_token_bar(self, chat_id, state=None)` | chat, optional state | `None` | true counts or estimate → `_set_token_counts` | Emits signal |
| `def _set_loading(self, chat_id, loading)` | chat, flag | `None` | dedupe → `state.is_loading` → emit `chat_state_changed` | Emits signal |

## Module-level helpers

| Signature | Inputs | Output | Flow / purpose |
|---|---|---|---|
| `def _content_hash(data: str \| list) -> str` | string or JSON list | 16-char blake2b hex | Hash for render planning |
| `def _extract_text_from_multimodal(content_parts: list) -> str` | multimodal parts | Joined text or `"[IMAGE]"` | Pulls `type == "text"` parts |
| `def normalize_content(content: str \| list) -> str` | content | String | Normalises content for hashing/display |
| `def _assistant_decision(msg: dict) -> dict` | assistant message | Decision dict | Thinking/response/tool-call state |
| `def _is_waiting_for_assistant(state: ChatState, messages) -> bool` | state, messages | Bool | Busy with no assistant content yet |
| `def _count_trailing_tool_results(messages, after_idx) -> int` | messages, index | Count | Consecutive `role == "tool"` messages |
| `def _compute_assistant_keys(msg, messages, idx, is_last_busy) -> list[str]` | message, messages, index, busy | Keys | Pending vs completed card keys |
| `def _accumulate_tokens(text, previous, current) -> int` | text, counted prefix, count | Updated count | Counts the appended suffix only |
