# qt.chat_controller — chat models, worker lifecycle & streaming apply

Source: `src/qt/chat_controller.py`

## Purpose

Owns one [`ChatListModel`](qt-models.md) per chat and the lifecycle of that
chat's [`ChatWorker`](chat-worker.md). The controller stays on the GUI thread: it
forwards user actions as worker commands and applies the ready row updates
(render plans, streaming body updates, result swaps) the workers emit. The
`Agent` and the render pipeline live on the worker thread, so chats stream and
render independently. Approval is a non-blocking command round-trip rather than a
blocked loop.

Related: [`chat-worker`](chat-worker.md), [`chat-render`](chat-render.md), [`qt-chat-state`](qt-chat-state.md), [`qt-chat-panel-model`](qt-chat-panel-model.md).

## Deliverables

- Per-chat `ChatListModel` cache; the active chat is exposed to a panel through
  [`ChatPanelModel`](qt-chat-panel-model.md).
- `attach_worker(chat_id, agent)` — ensure a worker exists and wire its signals.
- `set_visible_chats(ids)` — record which chats are shown in a panel.
- `prepare_rebuild(chat_id)` — for a **cold** model only, sets the loading
  overlay and blanks it synchronously. A populated model is left intact.
- `rebuild_chat_display(chat_id)` — `prepare_rebuild` + `worker.request_rebuild()`
  for a chat with an attached worker; used by the session controller's
  `_rebuild_changed_panels` when a split/move rebinds a panel to a different
  chat. A populated model is merged; chats without a worker are skipped and
  hydrated by the session controller's `_open_changed_panels` instead.
- Per-chat action slots (`_handle_send_for`, `_handle_stop_for`,
  `_handle_regenerate_for`, `_handle_delete_turn_for`, `_handle_regenerate_from_for`,
  `_handle_approve_for`, `_handle_deny_for`) plus focused-chat wrappers.
- `chat_state_changed(chat_id)` / `chat_tokens_changed(chat_id)` /
  `config_updated(chat_id, result)` signals for panels, tokens, and config sync.
- Transcript pre-warm: `prewarm_chat(chat_id)` renders a chat's transcript
  without showing it, `wait_until_ready(chat_id)` waits for a chat's first plan,
  `cancel_prewarms()` aborts in-flight pre-warms, and `forget_chat(chat_id)`
  drops per-chat pre-warm bookkeeping, the rendered model, and the connected
  worker for a deleted chat.
- `release_chat(chat_id)` — drop a non-visible chat's worker, agent, rendered
  model, and render cache so the transcript cache bounds memory. The worker is
  detached and stopped on a background thread so the GUI never waits for a
  render to finish.
- `release_all_chats(force=False)` — release every idle chat on session switch;
  `force=True` also releases visible/busy chats on window close.
- `shutdown_window()` — release every chat owned by a secondary window on close.
- `shutdown()` — stop every worker.

## Signals

| Signal | Payload | Meaning |
|---|---|---|
| `active_model_changed` | — | The focused `ChatListModel` changed |
| `approval_visibility_changed` | `bool` | Focused approval bar show/hide |
| `token_counts_changed` | `int, int` | Focused token counts (editor chat) |
| `toast_requested` | `str, str` | Message + toast level |
| `busy_changed` | `bool` | Focused generation running state |
| `loading_changed` | `bool` | Focused switch rebuild in progress |
| `chat_state_changed` | `str` | A chat's runtime state changed (per-panel refresh) |
| `chat_tokens_changed` | `str` | A chat's true token counts changed |
| `config_updated` | `str, object` | A worker live-config change (skill sync) |

## Steps / Flow

### Send (`_handle_send_for(chat_id, text)`)

1. Reject empty text, missing chat, or a busy chat with an error toast.
2. `_append_user_message` — optimistic user row.
3. `_launch_generation(chat_id, message)`.

### Launch (`_launch_generation` → `_start_turn`)

1. Set `is_busy`, clear `has_error`, bump `generation_id`; append the waiting
   scanner; refresh sidebar; emit `chat_state_changed`.
2. `_spawn(_start_turn(...))`: `session._hydrate_chat` → `attach_worker` →
   `worker.start_turn(message, gen_id)`.

### Worker apply slots

| Slot | Handler |
|---|---|
| `_on_plan_ready` | pre-warm chat → background batched insert (no overlay); else skip when `find_divergence == -1`; cold model → staged batched insert (`_apply_plan_staged`); populated model → `merge_items` (tail-only update); refresh token bar |
| `_on_stream_updated` | skip while `is_loading` (staged rebuild owns the model), else merge each `(row, values)` via `update_item` |
| `_on_result_swap` | `find_pending_result` → `replace_item`, else request a rebuild |
| `_on_turn_started` | refresh sidebar/state (busy already set) |
| `_on_turn_finished` | clear busy, reset turn, refresh, update buttons |
| `_on_approval_needed` | set pending info + text, show the approval bar |
| `_on_approval_cleared` | clear pending info, hide the bar |
| `_on_token_usage` | store true tokens, update the token bar |
| `_on_error` | set `has_error`, toast the brief |
| `_on_message_count` | store the count, debounce the sidebar refresh |
| `_on_compaction_ready` | create the compacted chat |
| `_on_config_updated` | forward via `config_updated` |

### Commands

- `_handle_stop_for` → `worker.cancel_turn()` + clear approval.
- `_handle_approve_for` / `_handle_deny_for` → `worker.confirm_approval` /
  `deny_approval` + clear approval.
- `_handle_regenerate_for` / `_handle_regenerate_from_for` → `_spawn` an async
  method that hydrates, attaches the worker, and calls `worker.regenerate(...)` /
  `regenerate_from(...)`.
- `_handle_delete_turn_for` → `worker.delete_turn(msg_index)`, or a direct store
  edit when the chat has no live worker.
- `rebuild_chat_display` → `prepare_rebuild` + `worker.request_rebuild()`.

### Transcript pre-warm

`prewarm_chat(chat_id)` hydrates a non-visible, non-busy chat with `silent=True`,
attaches its worker, registers it in `_prewarm_chats`, and calls
`worker.request_prewarm_plan()`. That worker path builds the plan on the chat's
own worker thread, so the CPU-heavy Markdown/Pygments/LaTeX work never blocks the
GUI loop. `_on_plan_ready` sees the pre-warm flag and applies the plan through
`_apply_plan_prewarm`, which inserts rows in **small batches**
(`_PREWARM_INSERT_BATCH = 4`, `_PREWARM_TICK = 0.05 s`) with **no loading
overlay**; a per-chat `_prewarm_tokens` counter lets a newer plan supersede an
in-flight one. Completion adds the id to `_rendered_chats` and resolves the
pre-warm future.

`wait_until_ready(chat_id)` polls `_rendered_chats`, so the session controller can
wait for the active chat's full build before pre-warming the others. Activating a
chat that is still pre-warming calls `_cancel_prewarm`, which bumps the token,
resolves the future, and clears the partial model so the normal loading-overlay
staged build owns it. `cancel_prewarms()` is used on session switch.

`release_chat(chat_id)` is called by the session controller's transcript LRU
eviction. It drops the chat's `ChatListModel` reference, detaches its worker,
removes the agent from `chat_manager`, and drops all per-chat bookkeeping. The
worker is stopped on a background thread so a long prewarm render cannot freeze
the GUI. The chat stays on disk and is re-hydrated on the next activation.
`release_all_chats()` releases idle chats on a session switch; `shutdown_window()`
forces the same release for every chat owned by a closing secondary window.

### Activation / loading overlay

`_handle_chat_activated` sets loading **only when the chat's model is cold**
(empty), bumps the switch generation, and spawns `_activate_async`: wait
`_REBUILD_PAINT_DELAY`, hydrate, attach the worker, then `worker.set_visible(True)`.
`set_visible` already emits a plan on `False → True`, so no second
`request_rebuild()` is issued. The resulting `_on_plan_ready`:

1. If `model.find_divergence(keys) == -1`, the model is already current → clear
   loading and do nothing.
2. Else if loading and the model is cold (or a staged apply is in flight), apply
   the rows in batches (`_apply_plan_staged`) behind the overlay; a per-chat
   staged token makes a newer apply supersede an in-flight one.
3. Else merge the plan into the populated model with `merge_items`, preserving
   existing delegates and updating only the changed tail.

The staged-insert budget is tuned low for snappy switches (`_RENDER_INSERT_BATCH`
= 16, tick target 0.25 s), and `_REBUILD_PAINT_DELAY` = 0.02 s. In QML the
overlay holds for 200 ms minimum after the build finishes.

`prepare_rebuild(chat_id)` sets loading and blanks the model **only when it is
cold** (`set_items([], [])`). `rebuild_chat_display(chat_id)` builds on it: when
a split/move rebinds a panel to a different chat (fixed slots keep every other
panel's delegate intact), the session controller calls it for the changed slots
only. A cold chat's non-virtualized card repeater binds an empty model and paints
the spinner while its worker re-renders in staged batches; a populated chat is
merged in place. Chats without an attached worker are skipped so no overlay is
left showing — the session controller's `_open_changed_panels` then opens those
cold chats, which hydrates them and attaches their worker.

## Function Reference

| Signature | Inputs | Output | Flow | Side effects |
|---|---|---|---|---|
| `def build(self)` | — | `None` | reset caches | — |
| `def shutdown(self)` | — | `None` | `stop_all_workers()` | joins threads |
| `def set_visible_chats(self, chat_ids)` | ids | `None` | push visibility to workers | — |
| `def _is_visible(self, chat_id)` | chat | bool | visible set check | — |
| `def model_for(self, chat_id)` | chat | `ChatListModel` | create on demand | inserts into `_models` |
| `def attach_worker(self, chat_id, agent)` | chat, agent | `ChatWorker` | ensure + connect signals + set visibility | starts a thread |
| `def prepare_rebuild(self, chat_id)` | chat | `None` | cold model → show loading + blank synchronously | No-op for a populated model |
| `def rebuild_chat_display(self, chat_id)` | chat | `None` | `prepare_rebuild` + worker rebuild request | Skips chats with no attached worker |
| `async def prewarm_chat(self, chat_id, timeout=15.0)` | chat, timeout | `None` | hydrate (silent) + attach worker + worker-thread plan + await future | No overlay; keeps the worker alive |
| `async def wait_until_ready(self, chat_id, timeout=15.0)` | chat, timeout | `None` | poll `_rendered_chats` | Returns on timeout |
| `def cancel_prewarms(self)` / `def cancel_prewarm(self, chat_id)` / `def forget_chat(self, chat_id)` | — / chat / chat | `None` | abort in-flight pre-warms / drop bookkeeping, rendered model, and connected worker | Clears partial models |
| `def release_chat(self, chat_id, *, force=False)` | chat, force | `None` | drop model reference → detach worker (background stop) → drop agent/bookkeeping | Frees Python and QML memory without blocking the GUI |
| `def release_all_chats(self, *, force=False)` | force | `None` | release every connected chat; force also clears all bookkeeping | Used on session switch and window close |
| `def shutdown_window(self)` | — | `None` | force-release every owned chat, cancel tasks | Used on secondary window close |
| `async def _apply_plan_prewarm(self, chat_id, model, items, keys, token)` | chat, model, rows, token | `None` | small batched insert without overlay | Resolves the pre-warm future |
| `def _model_needs_build(self, chat_id)` | chat | bool | `True` when the model is missing or empty | — |
| `def _handle_chat_activated(self, chat_id)` | chat | `None` | loading (cold only) + spawn activation | — |
| `async def _activate_async(self, chat_id, generation)` | chat, gen | `None` | hydrate + `set_visible(True)` (emits the plan) | — |
| `def _launch_generation(self, chat_id, message)` | chat, text | `None` | busy + scanner + spawn | mutates state |
| `async def _start_turn(self, chat_id, message, gen)` | chat, text, gen | `None` | hydrate + worker turn | — |
| `async def _regenerate(self, chat_id)` | chat | `None` | worker regenerate | — |
| `async def _regenerate_from(self, chat_id, msg_index)` | chat, index | `None` | worker regenerate_from | — |
| `def _delete_stored_turn(self, chat_id, msg_index)` | chat, index | `None` | store edit for non-live chat | writes store |
| `@Slot(str, object) def _on_plan_ready(self, chat_id, plan)` | chat, plan | `None` | no-op / staged / `merge_items` | mutates model |
| `async def _apply_plan_staged(self, chat_id, model, items, keys, token)` | chat, model, rows | `None` | batched insert | clears loading |
| `@Slot(str, object) def _on_stream_updated(self, chat_id, updates)` | chat, updates | `None` | skip while loading, else `update_item` per row | mutates model |
| `@Slot(str, str, object, str) def _on_result_swap(self, chat_id, tool_id, item, key)` | chat, tool id, item, key | `None` | replace pending row | mutates model |
| `@Slot(str, int) def _on_turn_started/_on_turn_finished(self, chat_id, gen)` | chat, gen | `None` | refresh state/sidebar | emits signals |
| `@Slot(str, object) def _on_approval_needed(self, chat_id, event)` | chat, event | `None` | show approval | emits signals |
| `@Slot(str) def _on_approval_cleared(self, chat_id)` | chat | `None` | hide approval | emits signals |
| `@Slot(str, int, int) def _on_token_usage(self, chat_id, in, out)` | chat, counts | `None` | store + token bar | emits signal |
| `@Slot(str, str, str) def _on_error(self, chat_id, brief, detail)` | chat, messages | `None` | set error + toast | emits signal |
| `@Slot(str, int) def _on_message_count(self, chat_id, count)` | chat, count | `None` | store + sidebar | — |
| `@Slot(str, str) def _on_compaction_ready(self, chat_id, summary)` | chat, summary | `None` | create compacted chat | writes store |
| `@Slot(str, object) def _on_config_updated(self, chat_id, result)` | chat, result | `None` | forward `config_updated` | emits signal |
| `def _append_user_message(self, chat_id, text)` / `_append_waiting_placeholder` | chat | `None` | optimistic `append_item` | inserts rows |
| `def _refresh_sidebar(self)` | — | `None` | debounced off-thread refresh | — |
| `def _spawn(self, coro)` | coro | `None` | `ensure_future` + track | — |

`_content_hash` builds the optimistic user-row key; `delete_bounds` (from
`chat_render`) maps a card to its message range for non-live deletes.
