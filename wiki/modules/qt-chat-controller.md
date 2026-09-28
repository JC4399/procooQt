# qt.chat_controller — chat rendering, streaming & approval

Source: `src/qt/chat_controller.py`

## Purpose

Owns one [`ChatListModel`](#per-chat-model-cache) per chat and drives the ReAct
event loop for every live chat. Rendering is gated on a **visible-chat set** so
up to four split panels can stream independently. `chat.messages` stays
canonical: the render plan is derived from it, diffed by content hash, and
clipped into the model. Approval blocks the loop on an `asyncio.Event`. Because
the app runs a single qasync loop on the GUI thread, streaming keeps work small
and off the critical path: per-message items are memoized by content hash,
incremental Markdown re-renders only the trailing block (response) or writes
escaped plain text (thinking), the response render runs on a worker thread, and
the sidebar refresh is debounced and offloaded.

## Deliverables

- Per-chat `ChatListModel` cache; the active chat is exposed to a panel through
  [`ChatPanelModel`](qt-chat-panel-model.md), not directly.
- `set_visible_chats(ids)` — the set of chats currently shown in a panel.
- `add_visible_chat(chat_id)` / `remove_visible_chat(chat_id)` — chats rendered
  outside a panel (the editor chat), so streaming is still painted.
- Per-chat action slots (`_handle_send_for`, `_handle_stop_for`,
  `_handle_regenerate_for`, `_handle_approve_for`, `_handle_deny_for`) plus
  focused-chat wrappers.
- The streaming generation loop split into hydrate / consume-events / cleanup
  phases.
- Content-hash rendering (`_rebuild_chat_display` → `_compute_render_plan` →
  `_build_plan` → `diff_update`) with a per-chat item cache, and the plan
  computed off the GUI thread for panel switches.
- The `_PlanBuilder`, `_StagedBuildState` and `_RenderIndices` dataclasses.
- Tool approval via `asyncio.Event`, stop/regenerate, and automatic chat
  compaction.
- Per-card history editing: `_handle_delete_turn_for` removes the turn a card
  belongs to; `_handle_regenerate_from_for` truncates from a user card and
  regenerates.
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

1. Clear `state.has_error`; set `state.is_busy = True`; increment
   `state.generation_id` (`gen_id`).
2. `_append_waiting_placeholder(chat_id)` — the `w:pending` scanner renders in
   the same frame as the user card, before hydration.
3. `_refresh_sidebar()`; emit `chat_state_changed(chat_id)`.
4. `_spawn(_run_chat_loop(message, gen_id, chat_id))`.

### `_run_chat_loop` (phases)

1. **Hydrate** — `_hydrate_phase(chat_id, gen_id)` calls
   `session._hydrate_chat(...)`. On failure, clear busy, set `has_error`,
   rebuild/refresh.
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
| `token_usage` | Set `true_input_tokens` / `true_output_cum`; when visible, `_update_token_bar` refreshes the bar |
| `done` | Break out of the loop |
| `error` | Set `state.has_error`, toast the `brief` (when visible), and break |

After each event, a change in `len(chat.messages)` triggers `_refresh_sidebar()`,
and when visible `_render_active_event(...)` updates the display.

### Per-event rendering (`_render_active_event`)

- If the message count changed and the event is a `tool_result`, swap the
  pending result card in place via `_swap_pending_result_card(chat_id, ...)`.
- Otherwise rebuild the display.
- If unchanged and the last message is not an assistant message, rebuild; else
  `await _update_live_assistant(chat_id, state)` (throttled, and for the response
  body offloaded to a worker thread).

### Rebuild pipeline

`_compute_render_plan(chat_id)` resolves the message list and context snapshot
(for a live chat it reuses the state's cached `context_snapshot` instead of
re-reading the chat file), then `_build_plan` produces `(keys, items, indices)`
in a single pass. `_PlanBuilder.emit` looks each key up in the chat state's
`item_cache`, so only messages whose content actually changed are re-rendered;
streaming entries are marked `cacheable=False` because their keys change each
tick. Every message-derived key embeds the message index (`u:{i}:…`, `t:{i}:…`,
`r:{i}:…`, `c:{i}:…`, `tr:{i}:…`) and the item carries the matching `msg_index`
role, so the card actions always target the right message and a matched row can
never retain a stale index. Messages older than `_COLLAPSE_OLDER_THAN` (12) are
built with `collapsed=True` and a `:c` key suffix, so they start collapsed in QML
(their rich text is never laid out) and ageing a message out rebuilds it once.
The plan does not mutate Qt models, so it is safe on a worker thread.

`_rebuild_chat_display(chat_id)` applies the plan synchronously; after a panel
switch `_rebuild_chat_display_staged(chat_id)` builds it behind the loading
overlay, inserting `_RENDER_INSERT_BATCH` (8) rows per tick (clamped 6–20 ms
toward a 0.6 s target). The plan is computed off-thread.
`_skip_staged_build()` flushes the remainder before a user action;
`_cancel_staged_build()` drops it on a new activation.

### Live update throttling (`_update_live_assistant`)

- **Structural** changes force an immediate `_rebuild_chat_display`, which now
  reuses cached items for all unchanged messages.
- A pending thinking/response card whose row does not exist yet rebuilds
  immediately.
- **Content-only** updates and streaming-tool-call argument changes are throttled
  to `_STREAM_UPDATE_INTERVAL` (0.08 s) and applied in place by
  `_apply_streaming_item_updates`. Thinking is escaped via
  [`thinking_body`](qt-chat-items.md); the response is rendered through the
  card's [`IncrementalMarkdown`](qt-markdown.md#incremental-streaming-renderer-incrementalmarkdown)
  on a worker thread (`asyncio.to_thread`), so parse/highlight/sanitize never
  block the GUI thread.

### Sidebar refresh (`_refresh_sidebar`)

`_refresh_sidebar` only sets a dirty flag and starts `_refresh_sidebar_loop`, a
single task that waits for a `_SIDEBAR_REFRESH_DEBOUNCE` (0.3 s) quiet period,
then calls `SessionController.refresh_model_async` — the disk scan runs on a
worker thread and is applied back on the GUI thread. This coalesces the burst of
message-count changes during a stream.

### Approval (`_handle_approval`)

1. Create `state.approval_event`; set `pending_tool_info`, `approval_text`.
2. Refresh the sidebar; emit `chat_state_changed(chat_id)`; when visible, rebuild.
3. `await state.approval_event.wait()` — the loop is blocked here.
4. Clear pending/text; refresh; emit `chat_state_changed`.

`_approve(chat_id)`, `_deny(chat_id, reason)`, and `_stop_generation(chat_id)`
call `chat.approve_tool` / `chat.deny_tool` and `set()` the event.

### Stop / regenerate / approve / deny

- `_handle_stop_for(chat_id)` → `_stop_generation(chat_id)`: mark the chat
  `has_error` (stopped turns show a red tab dot) then cancel the run.
- `_handle_regenerate_for(chat_id)` → `_regenerate(chat_id)`: find the last user
  message, trim the stored turn (`_trim_stored_chat`), drop delta banners, remove
  the live chat, rebuild, relaunch.
- `_handle_approve_for(chat_id)` → `_approve`; `_handle_deny_for(chat_id, reason)`
  → `_deny`.

### Delete turn / regenerate from a card

Every rendered card carries the `msg_index` of the message it was built from (in
the item and in its render key, so a matched row can never keep a stale index;
`-1` for derived cards). Card actions from `CardBase.qml` route here:

- `_handle_delete_turn_for(chat_id, msg_index)` → `_delete_turn` (synchronous):
  rejects a busy chat, then resolves the live `Agent` messages (mutated in place,
  `_current_assistant_msg` reset) or the stored messages when the chat is not
  hydrated. `_round_bounds` returns the `[start, end)` of the turn: it walks back
  to the nearest user message (over any immediately-preceding injected system
  messages) and forward to the next user message, so the prompt, assistant reply,
  tool calls, and tool results are removed together and the remaining history
  stays LLM-valid. The truncated list is persisted (`_save_current_chat_for` for
  a live chat, a direct store save otherwise), `state.item_cache` is cleared, and
  the display and sidebar are rebuilt.
- `_handle_regenerate_from_for(chat_id, msg_index)` → `_regenerate_from`
  (async): rejects a busy chat or a non-user index, reads the message text via
  `normalize_content`, writes `messages[:msg_index]` to the store, drops delta
  banners, removes the live chat, clears the item cache, rebuilds, and calls
  `_launch_generation(chat_id, text)` — discarding that user message and
  everything after it before re-running the turn.

Both actions are inert while the chat is busy (`actionsEnabled` in QML plus the
controller guard), matching the `_handle_regenerate_for` behaviour.

### Compaction

`_compact_chat(chat_id, chat)` checks `chat.check_limit_exceeded()`; toasts when
visible, `await chat.summarize()`, and on success calls `_create_compacted_chat`.
That generates a new id, copies `skills_config`, `session`, `model_name`, and
`context_snapshot`, seeds `messages` with the summary, records `summary_of`, and
`session.open_chat_after(chat_id, new_id)`.

### Token accounting

`_update_token_bar(chat_id, state)` shows only the true API counts reported by
`token_usage` (`state.true_input_tokens` / `state.true_output_cum`); it never
falls back to a word-count estimate, so a chat with no response yet shows zero.
`ChatPanelModel` reads the same values through `SessionController._panel_runtime`;
`_set_token_counts` emits `token_counts_changed` for the focused chat.
`_accumulate_tokens` counts only the appended suffix of each text field and feeds
the per-card `tk` estimate, which is independent of the token bar.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def build(self) -> None` | — | `None` | reset `_models`, `_visible_chat_ids`, `_extra_visible_chats`, `active_chat_id` | — |
| `def set_visible_chats(self, chat_ids: set[str]) -> None` | visible chat ids | `None` | store `_visible_chat_ids` | Gates rendering |
| `def add_visible_chat(self, chat_id: str) -> None` | chat id | `None` | add to `_extra_visible_chats` | Keeps a non-panel chat (editor chat) visible |
| `def remove_visible_chat(self, chat_id: str) -> None` | chat id | `None` | discard from `_extra_visible_chats` | — |
| `def _is_visible(self, chat_id: str) -> bool` | chat id | Bool | `chat_id in _visible_chat_ids or _extra_visible_chats` | — |
| `@Property(QObject, notify=active_model_changed) def activeModel(self)` | — | Focused model or `None` | `_models.get(active_chat_id)` | Legacy |
| `def model_for(self, chat_id: str) -> ChatListModel` | chat id | Chat model | create on demand | Inserts into `_models` |
| `def _refresh_sidebar(self) -> None` | — | `None` | set dirty flag → start `_refresh_sidebar_loop` if idle | Debounced; no blocking I/O |
| `async def _refresh_sidebar_loop(self) -> None` | — | `None` | wait for quiet period → `session.refresh_model_async()` | Off-thread disk scan |
| `def _spawn(self, coro: Coroutine) -> None` | coroutine | `None` | `ensure_future` → track → discard | Fire-and-forget |
| `@Slot(str, str) def _handle_send_for(self, chat_id, text)` | chat, text | `None` | validate → append → launch | Error toasts |
| `@Slot(str) def _handle_send(self, text)` | text | `None` | `_handle_send_for(active_chat_id, text)` | — |
| `@Slot(str) def _handle_stop_for(self, chat_id)` | chat | `None` | `_spawn(_stop_generation(chat_id))` | — |
| `@Slot(str) def _handle_regenerate_for(self, chat_id)` | chat | `None` | `_spawn(_regenerate(chat_id))` | — |
| `@Slot(str, int) def _handle_delete_turn_for(self, chat_id, msg_index)` | chat, source message index | `None` | `_delete_turn(chat_id, msg_index)` | Busy guard + toast |
| `@Slot(str, int) def _handle_regenerate_from_for(self, chat_id, msg_index)` | chat, source user index | `None` | `_spawn(_regenerate_from(chat_id, msg_index))` | Busy guard + toast |
| `@Slot(str) def _handle_approve_for(self, chat_id)` | chat | `None` | `_spawn(_approve(chat_id))` | — |
| `@Slot(str, str) def _handle_deny_for(self, chat_id, reason)` | chat, reason | `None` | `_spawn(_deny(chat_id, reason))` | — |
| `@Slot(str) def _handle_chat_switch_started(self, chat_id)` | chat | `None` | `_cancel_staged_build()` → `_set_loading(chat_id, True)` | Shows the overlay at the user action |
| `@Slot(str) def _handle_chat_activated(self, chat_id)` | chat (may be `""`) | `None` | set focused id → clear caches → emit → `_set_loading(chat_id, True)` → `_spawn(_rebuild_after_switch)` | Emits `active_model_changed` |
| `async def _rebuild_after_switch(self, chat_id)` | chat | `None` | sleep(0) → visible check → staged rebuild → `_set_loading(chat_id, False)` → emit `chat_state_changed` | — |
| `def _launch_generation(self, chat_id, message)` | chat, text | `None` | clear `has_error` + busy + bump `generation_id` → append scanner → refresh → emit state → spawn loop | Mutates state |
| `async def _run_chat_loop(self, message, gen_id, chat_id)` | message, generation, chat | `None` | hydrate → run → reconcile → consume → finalize → compact on limit | Cancellable; persists |
| `async def _hydrate_phase(self, chat_id, gen_id)` | chat, generation | Live chat or `None` | `_hydrate_chat`; on failure clear busy + set `has_error`/rebuild | Side effects on failure |
| `async def _consume_events(self, chat, chat_id, state, task)` | live chat, id, state, task | `None` | 0.1s poll → per-type branches (`error` sets `has_error`) | May block on approval |
| `async def _render_active_event(self, event, chat, chat_id, state, msg_count, last_rendered)` | event + render context | New count | swap result vs rebuild vs live | May mutate model; awaits worker render |
| `def _finalize_turn(self, chat_id, state, gen_id)` | chat, state, generation | `None` | clear busy (`has_error` left as-is) → rebuild → reset → save → refresh → emit state | Persists |
| `async def _stop_generation(self, chat_id)` | chat | `None` | mark `has_error` → deny pending → set event → cancel task | Cancels task |
| `async def _approve(self, chat_id)` | chat | `None` | `approve_tool` → set event → emit state | Releases approval |
| `async def _deny(self, chat_id, reason)` | chat, reason | `None` | `deny_tool` → set event → emit state | Releases approval |
| `async def _regenerate(self, chat_id)` | chat | `None` | find last user → trim → drop deltas → remove live → rebuild → `_launch_generation` | Error toasts |
| `def _delete_turn(self, chat_id, msg_index)` | chat, source message index | `None` | guard busy → live/stored messages → `_round_bounds` → delete range → persist → clear cache → rebuild → refresh sidebar | Mutates messages; error toasts |
| `async def _regenerate_from(self, chat_id, msg_index)` | chat, source user index | `None` | guard busy/non-user → read text → store `messages[:msg_index]` → drop deltas → remove live → rebuild → `_launch_generation` | Writes store; error toasts |
| `def _find_last_user_message(self, chat_id)` | chat | Last user text | live → stored messages | — |
| `def _trim_stored_chat(self, chat_id)` | chat | `None` | pop trailing non-user then user → save | Writes store |
| `async def _handle_approval(self, chat_id, event, state)` | chat, tool_call event, state | `None` | set event/pending → emit → await → clear | Blocks loop |
| `def _set_approval_visible(self, visible: bool)` | visibility | `None` | dedupe → store → emit | Focused bar |
| `async def _compact_chat(self, chat_id, chat)` | chat, live agent | `None` | limit check → toast → summarize → `_create_compacted_chat` | Toasts |
| `async def _create_compacted_chat(self, chat_id, summary)` | old id, summary | `None` | new record seeded with summary → `session.open_chat_after` | Writes store |
| `@Slot(str) def rebuild_chat_display(self, chat_id)` | chat | `None` | no-op on empty → `_rebuild_chat_display` | Public entry for skill sync |
| `def _compute_render_plan(self, chat_id)` | chat | `(keys, items, snapshot, indices)` | live chat reuses cached snapshot + item cache; else load stored → `_build_plan` | Pure; worker-thread safe |
| `def _apply_render_indices(self, state, indices)` | state, indices | `None` | copy row indices onto state | GUI thread only |
| `def _rebuild_chat_display(self, chat_id)` | chat | `None` | skip staged → plan → indices → `diff_update` → keys → tokens | Mutates model/state |
| `async def _rebuild_chat_display_staged(self, chat_id)` | chat | `None` | off-thread plan → indices → `_StagedBuildState` → batched inserts | Aborts on cancel/visibility change |
| `def _skip_staged_build(self)` / `def _cancel_staged_build(self)` | — | `None` | flush / drop the staged build | — |
| `def _build_plan(self, state, messages, snapshot)` | state, messages, snapshot | `_PlanBuilder` | banners → user/assistant/tool → trailing `w:pending`, each item memoized by key with its message index embedded (`u:{i}:…` etc.) and set as the `msg_index` role; messages older than `_COLLAPSE_OLDER_THAN` get `collapsed=True` + `:c` key suffix | Populates `state.item_cache` |
| `def _build_assistant_plan(self, builder, msg, messages, idx, is_last_busy, collapsed)` | builder, message, messages, index, busy, collapsed | `None` | completed assistant: thinking/response/tool-call items | Emits cacheable items |
| `def _build_streaming_assistant_plan(self, builder, msg, d, messages, idx)` | builder, message, decision, messages, index | `None` | busy assistant: pending/completed cards, records indices | Emits non-cacheable items |
| `def _append_user_message(self, chat_id, text)` | chat, text | `None` | `append_item(user item, key)` | Inserts a row |
| `def _append_waiting_placeholder(self, chat_id)` | chat | `None` | `append_item(waiting item, "w:pending")` | Inserts scanner |
| `def _swap_pending_result_card(self, chat_id, tool_call_id, tool_name, content)` | chat, tool call, content | `None` | find pending row → replace; else rebuild | Replaces a row |
| `async def _update_live_assistant(self, chat_id, state)` | chat, state | `None` | structural rebuild vs throttled body update | Mutates model/state |
| `async def _apply_streaming_item_updates(self, chat_id, state, ...)` | chat, state, texts, flags | `None` | accumulate tokens → plain thinking / threaded incremental response → `update_item` | Updates rows/state |
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
| `def _round_bounds(messages, msg_index) -> tuple[int, int]` | messages, source index | `(start, end)` | Half-open turn range: back to nearest user message (over preceding system messages), forward to next user message |
| `def _accumulate_tokens(text, previous, current) -> int` | text, counted prefix, count | Updated count | Counts the appended suffix only |

`_PlanBuilder` (class) accumulates keys/items/indices and owns the
cache-reuse-by-key logic described above.
