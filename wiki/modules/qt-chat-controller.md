# qt.chat_controller — chat rendering, streaming & approval

Source: `src/qt/chat_controller.py`

## Purpose

Owns one [`ChatListModel`](#per-session-model-cache) per live session and drives
the ReAct event loop. The class merges the Flet edition's `chat_panel`
(build/render) and `chat_loop` (events/streaming) mixins into a single
`QObject`. `session.messages` stays canonical: the render plan is derived from
it, diffed by content hash, and clipped into the model. Approval blocks the loop
on an `asyncio.Event`, and long streams are rendered with throttled in-place
updates.

## Deliverables

- Signals and properties that drive `ChatPanel.qml`, `ApprovalBar.qml`, and
  `TokenBar.qml`.
- A per-session `ChatListModel` cache selected by `activeModel`.
- The streaming generation loop split into hydrate / consume-events / cleanup
  phases.
- Incremental content-hash rendering (`rebuild_chat_display` →
  `_compute_render_keys` → `_build_items` → `diff_update`).
- Tool approval via `asyncio.Event`, stop/regenerate, and automatic session
  compaction.

## Signals

| Signal | Payload | Meaning |
|---|---|---|
| `active_model_changed` | — | The active `ChatListModel` changed |
| `approval_visibility_changed` | `bool` | Approval bar show/hide |
| `token_counts_changed` | `int, int` | Input/output token counts |
| `toast_requested` | `str, str` | Message + toast level |
| `busy_changed` | `bool` | Generation running state |
| `loading_changed` | `bool` | Session-switch rebuild in progress |

## Properties

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `activeModel` | `ChatListModel \| None` | `active_model_changed` | Model for the active session |
| `approvalVisible` | `bool` | `approval_visibility_changed` | Whether the approval bar is shown |
| `approvalText` | `str` | `approval_visibility_changed` | Approval prompt text |
| `busy` | `bool` | `busy_changed` | Active session is generating |
| `loading` | `bool` | `loading_changed` | Chat display is rebuilding after a switch |
| `inputTokens` | `int` | `token_counts_changed` | Context (input) tokens |
| `outputTokens` | `int` | `token_counts_changed` | Cumulative output tokens |

## Per-session model cache

`_models: dict[str, ChatListModel]` holds one model per session.
`model_for(session_id)` creates on demand; `activeModel` returns
`_models.get(active_session_id)` (or `None`). `_handle_session_activated`
points the active id at the right model and clears its render caches before
rebuilding.

## Steps / Flow

### Send (`_handle_send`)

1. Reject empty text, missing active session, or a busy session with an error
   toast.
2. `_append_user_message(message)` — optimistic `append_item` so the bubble
   appears immediately.
3. `_launch_generation(message)`.

### Launch (`_launch_generation`)

1. Set `state.is_busy = True`; increment `state.generation_id` (captured as
   `gen_id`).
2. `_refresh_sidebar()`; `_update_button_state()`.
3. `_spawn(_run_chat_loop(message, gen_id, session_id))`.

### `_run_chat_loop` (phases)

1. **Hydrate** — `_hydrate_phase(session_id, gen_id)`: `await
   session._hydrate_session(...)`. On failure, when the generation is still
   current, rebuild the display if active, clear busy, update buttons, refresh
   the sidebar, and return.
2. Start `task = asyncio.ensure_future(session.run(message))`; store it as
   `state.active_task`.
3. **Consume** — `await _consume_events(session, session_id, state, task)`; then
   `await task` if still pending. `asyncio.CancelledError` cancels the task.
4. **Cleanup** — `finally: _finalize_turn(...)` clears busy (when the generation
   is current), rebuilds the active display, resets the turn, saves the session,
   refreshes the sidebar, and updates buttons.
5. After cleanup, if `session.check_limit_exceeded() is not None`, run
   `_compact_session`.

### Consume events (`_consume_events`)

Drains `session.event_queue` while the task is pending or the queue is
non-empty, reading with `asyncio.wait_for(..., timeout=0.1)` (a timeout simply
loops). By `event["type"]`:

| Event type | Handling |
|---|---|
| `tool_call` (mode `ask`) | `await _handle_approval(session_id, event, state)` — blocks |
| `tool_call` (other modes) | No direct branch; rendered through the message list |
| `tool_result` | Append to `state.tool_results` |
| `token_usage` | Set `true_input_tokens` / `true_output_cum`; update the token bar when active |
| `done` | Break out of the loop |
| `error` | Toast the `brief` (when active) and break |

After each event, a change in `len(session.messages)` triggers
`_refresh_sidebar()`, and when the session is active `_render_active_event(...)`
updates the display.

### Per-event rendering (`_render_active_event`)

- If the message count changed and the event is a `tool_result`, swap the
  pending result card in place via `_swap_pending_result_card`.
- Otherwise rebuild the display.
- If the message count is unchanged and the last message is not an assistant
  message, rebuild; else `_update_live_assistant` (throttled).

### Rebuild pipeline

`_rebuild_chat_display(session_id)` loads the state, model, stored snapshot, and
live messages (falling back to stored messages), then:

1. `_compute_render_keys(state, messages, snapshot)` — one key per emitted item.
2. `_build_items(state, messages, snapshot)` — role-keyed item dicts aligned with
   the keys.
3. `model.diff_update(items, keys)` — the `QAbstractListModel` helper removes rows
   from the first divergence and appends the new suffix.
4. Store `rendered_item_keys`; mark `init_banner_displayed` when a snapshot
   exists; update the token bar when active.

`_compute_render_keys` emits `b:i` for the initial context banner, `b:d:<hash>`
for each delta banner in `context_banners_data`, `u:<hash>` for user messages,
one or more keys for assistant messages from `_compute_assistant_keys` (pending
cards are keyed by live token counts, completed cards by content hash), and
`tr:<name>:<hash>` for tool results. `_build_items` mirrors the same order using
the `chat_items` / `context_banner` builders and records
`thinking.item_index`, `response.item_index`, and `tool_call_indices` so live
updates can find the rows later.

### Live update throttling (`_update_live_assistant`)

- **Structural** changes — tool-call count, tool-result count, or streaming
  tool calls that appear before any tool-call row exists — force an immediate
  `_rebuild_chat_display`.
- A response whose pending row does not exist yet rebuilds when the 1-second
  `last_rebuild_time` gate allows.
- **Content-only** changes (thinking/response text) and streaming-tool-call
  argument updates are throttled to one second via `last_content_update_time`
  and applied in place by `_apply_streaming_item_updates`, which rewrites the
  pending card's `TOKEN_TEXT` role.
- `_track_rendered_state` snapshots the rendered text/counts so the next call
  can diff.

### Approval (`_handle_approval`)

1. Create `state.approval_event = asyncio.Event()`; set `pending_tool_info`,
   `approval_text` (`"Approve <name>?"`).
2. Refresh the sidebar; when active, rebuild, publish `approvalText`, and show
   the bar.
3. `await state.approval_event.wait()` — the loop is blocked here.
4. Clear `pending_tool_info`/`approval_text`, refresh the sidebar, and hide the
   bar when active.

`_approve`, `_deny`, and `_stop_generation` each call `session.approve_tool` /
`session.deny_tool` and then `set()` the event to release the loop.

### Stop / regenerate / approve / deny

- `_handle_stop` → `_stop_generation`: deny the pending tool, set the approval
  event, cancel `active_task`, update buttons, hide the approval bar.
- `_handle_regenerate` → `_regenerate`: find the last user message
  (`_find_last_user_message`), trim the stored turn (`_trim_stored_session`),
  drop delta banners, remove the live session, rebuild, and relaunch generation.
- `_handle_approve` → `_approve`; `_handle_deny(reason)` → `_deny`.

### Compaction

`_compact_session` reads `session.check_limit_exceeded()`; if set, toasts the
active session, `await session.summarize()`, and on success calls
`_create_compacted_session`. That helper generates a new id, copies
`skills_config`, `folder`, and `context_snapshot`, seeds `messages` with the
summary as a `user` message, records `summary_of`, prepends the id, refreshes
the model, and `await self.session._switch_to_session(new_id)`.

### Token accounting

`_update_token_bar(state)` prefers the true API counts when
`state.true_input_tokens > 0` (`true_output_cum` output), else the live
session's `_estimated_total` with zero output. `_set_token_counts` stores and
emits `token_counts_changed`. During streaming, `_accumulate_tokens` counts only
the newly appended suffix of each text field.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def build(self) -> None` | — | `None` | reset `_models`, `active_session_id = None` | — |
| `@Property(QObject, notify=active_model_changed) def activeModel(self) -> ChatListModel \| None` | — | Active model or `None` | `_models.get(active_session_id)` | — |
| `@Property(bool, notify=approval_visibility_changed) def approvalVisible(self) -> bool` | — | Bar visibility | returns `_approval_visible` | — |
| `@Property(str, notify=approval_visibility_changed) def approvalText(self) -> str` | — | Prompt text | returns `_approval_text` | — |
| `@Property(bool, notify=busy_changed) def busy(self) -> bool` | — | Busy state | returns `_busy` | — |
| `@Property(bool, notify=loading_changed) def loading(self) -> bool` | — | Loading state | returns `_loading` | — |
| `@Property(int, notify=token_counts_changed) def inputTokens(self) -> int` | — | Input tokens | returns `_input_tokens` | — |
| `@Property(int, notify=token_counts_changed) def outputTokens(self) -> int` | — | Output tokens | returns `_output_tokens` | — |
| `def model_for(self, session_id: str) -> ChatListModel` | session id | Chat model | create `ChatListModel` on demand | Inserts into `_models` |
| `def _refresh_sidebar(self) -> None` | — | `None` | `self.session._refresh_model()` | Emits `sessions_changed` |
| `def _spawn(self, coro: Coroutine) -> None` | coroutine | `None` | `ensure_future` → track in `_tasks` → discard on done | Fire-and-forget task |
| `@Slot(str) def _handle_send(self, text: str) -> None` | message text | `None` | validate → `_append_user_message` → `_launch_generation` | Error toasts; appends + launches |
| `@Slot() def _handle_stop(self) -> None` | — | `None` | `_spawn(_stop_generation)` | — |
| `@Slot() def _handle_regenerate(self) -> None` | — | `None` | `_spawn(_regenerate)` | — |
| `@Slot() def _handle_approve(self) -> None` | — | `None` | `_spawn(_approve)` | — |
| `@Slot(str) def _handle_deny(self, reason: str) -> None` | denial reason | `None` | `_spawn(_deny(reason))` | — |
| `@Slot(str) def _handle_session_activated(self, session_id: str) -> None` | new active id (may be `""`) | `None` | set id → clear caches → emit → `_set_loading(True)` → `_spawn(_rebuild_after_switch)` | Emits `active_model_changed` |
| `async def _rebuild_after_switch(self, session_id: str) -> None` | activated id | `None` | `await asyncio.sleep(0)` → stale check → rebuild → restore approval/buttons → loading off | Emits approval/loading signals |
| `def _launch_generation(self, message: str) -> None` | user text | `None` | busy + bump `generation_id` → refresh sidebar/buttons → spawn loop | Mutates state |
| `async def _run_chat_loop(self, message: str, gen_id: int, session_id: str) -> None` | message, generation id, session | `None` | hydrate → run task → consume → finalize → compact on limit | Cancellable; persists session |
| `async def _hydrate_phase(self, session_id: str, gen_id: int) -> Agent \| None` | session, generation | Live session or `None` | `_hydrate_session`; on failure clear busy/rebuild | Side effects on failure |
| `async def _consume_events(self, session: Agent, session_id: str, state: SessionState, task: asyncio.Task) -> None` | live session, id, state, task | `None` | 0.1s queue poll → per-type branches → sidebar/render after each event | Updates state; may block on approval |
| `def _render_active_event(self, event: dict, session: Agent, session_id: str, state: SessionState, msg_count: int, last_rendered: int) -> int` | event + render context | New last-rendered count | swap result vs rebuild vs `_update_live_assistant` | May mutate model |
| `def _finalize_turn(self, session_id: str, state: SessionState, gen_id: int) -> None` | session, state, generation | `None` | clear busy (if current) → rebuild → reset turn → save → refresh → buttons | Persists session; emits signals |
| `async def _stop_generation(self) -> None` | — | `None` | deny pending → set event → cancel task → buttons/approval off | Cancels task; logs |
| `async def _approve(self) -> None` | — | `None` | `approve_tool` → set event | Releases approval |
| `async def _deny(self, reason: str) -> None` | reason | `None` | `deny_tool(reason)` → set event | Releases approval |
| `async def _regenerate(self) -> None` | — | `None` | find last user → trim stored → drop deltas → remove live → rebuild → launch | Error toasts; mutates store |
| `def _find_last_user_message(self, session_id: str) -> str` | session id | Last user text | live messages → stored messages | — |
| `def _trim_stored_session(self, session_id: str) -> None` | session id | `None` | pop trailing non-user then the user message → save | Writes store |
| `async def _handle_approval(self, session_id: str, event: dict, state: SessionState) -> None` | session, tool_call event, state | `None` | set event/pending → show bar → `await event.wait()` → clear/hide | Blocks loop; emits signals |
| `def _set_approval_visible(self, visible: bool) -> None` | visibility | `None` | dedupe → store → emit `approval_visibility_changed` | Emits signal |
| `async def _compact_session(self, session_id: str, session: Agent) -> None` | session, live agent | `None` | limit check → toast → `summarize` → `_create_compacted_session` | Toasts; may fail gracefully |
| `async def _create_compacted_session(self, session_id: str, summary: str) -> None` | old id, summary | `None` | new record seeded with summary → prepend → refresh → switch | Writes store; switches |
| `@Slot(str) def rebuild_chat_display(self, session_id: str) -> None` | session id | `None` | no-op on empty → `_rebuild_chat_display` | Public entry for skill sync |
| `def _rebuild_chat_display(self, session_id: str) -> None` | session id | `None` | keys + items → `diff_update` → store keys → token bar | Mutates model |
| `def _compute_render_keys(self, state: SessionState, messages: list[dict], snapshot: dict \| None) -> list[str]` | state, messages, snapshot | Render keys | banners → user/assistant/tool keys | — |
| `def _build_items(self, state: SessionState, messages: list[dict], snapshot: dict \| None) -> list[dict]` | state, messages, snapshot | Chat items | banners → per-message builders | Resets card/row indices |
| `def _build_assistant_items(self, state: SessionState, msg: dict, messages: list[dict], idx: int, is_last_busy: bool, items: list[dict]) -> None` | state, message, context | `None` | streaming branch, else thinking/response/tool-call items | Appends to `items` |
| `def _build_streaming_assistant_items(self, state: SessionState, d: dict, messages: list[dict], idx: int, items: list[dict]) -> None` | state, decision dict, context | `None` | pending/completed thinking + response + tool calls + pending results | Records row indices |
| `def _append_user_message(self, text: str) -> None` | text | `None` | `model.append_item(user item, key)` | Inserts a row |
| `def _swap_pending_result_card(self, tool_call_id: str, tool_name: str, content: str) -> None` | tool call id/name, content | `None` | find pending row → replace item; else rebuild | Replaces a row |
| `def _update_live_assistant(self, state: SessionState) -> None` | state | `None` | structural rebuild vs 1s-throttled content update | Mutates model/state |
| `def _apply_streaming_item_updates(self, state: SessionState, thinking_text: str, content_text: str, streaming_tcs: list \| None, thinking_changed: bool, content_changed: bool) -> None` | current texts + flags | `None` | accumulate tokens → `update_item(TOKEN_TEXT)` | Updates rows/state |
| `def _track_rendered_state(self, state: SessionState) -> None` | state | `None` | snapshot last assistant text/counts | Mutates state |
| `def _update_token_bar(self, state: SessionState \| None = None) -> None` | optional state | `None` | true counts or estimate → `_set_token_counts` | Emits token signal |
| `def _set_token_counts(self, input_tokens: int, output_tokens: int) -> None` | counts | `None` | store + emit `token_counts_changed` | Emits signal |
| `def _update_button_state(self) -> None` | — | `None` | read busy → emit `busy_changed` if changed | Emits signal |
| `def _set_loading(self, loading: bool) -> None` | flag | `None` | dedupe → store → emit `loading_changed` | Emits signal |

## Module-level helpers

| Signature | Inputs | Output | Flow / purpose |
|---|---|---|---|
| `def _content_hash(data: str \| list) -> str` | string or JSON list | 16-char blake2b hex | Hash for render planning (lists are sorted-JSON encoded) |
| `def _extract_text_from_multimodal(content_parts: list) -> str` | multimodal parts | Joined text or `"[IMAGE]"` | Pulls `type == "text"` parts for display |
| `def normalize_content(content: str \| list) -> str` | content | String | Normalises message content for hashing/display |
| `def _assistant_decision(msg: dict) -> dict` | assistant message | Decision dict | Common thinking/response/tool-call state shared by keys and builders |
| `def _count_trailing_tool_results(messages: list[dict], after_idx: int) -> int` | messages, index | Count | Consecutive `role == "tool"` messages after the index |
| `def _compute_assistant_keys(state, msg, messages, idx, is_last_busy) -> list[str]` | state + message | Render keys | Pending cards keyed by live token counts; completed cards by content hash |
| `def _accumulate_tokens(text: str, previous: str, current: int) -> int` | full text, counted prefix, current count | Updated count | Counts only the appended suffix; recomputes on shrink |
