# chat_worker — per-chat worker threads

Source: `src/qt/chat_worker.py`

## Purpose

Runs each chat fully independently on its own `QThread`. Every `ChatWorker`
owns one `Agent` and its `ChatRenderer` and drives them inside a private
`asyncio` event loop, so a chat's network streaming, tool subprocesses, approval
waits, and Markdown rendering never block the GUI thread or other chats. The GUI
sends commands via `loop.call_soon_threadsafe` and applies the row updates the
worker emits as Qt signals.

Related: [`chat_render`](chat-render.md), [`chat-agent`](chat-agent.md), [`qt-chat-controller`](qt-chat-controller.md).

## Deliverables

- One `ChatWorker` per hydrated chat, created/started via the module registry.
- `plan_ready` / `stream_updated` / `result_swap` row payloads for the GUI model.
- `request_prewarm_plan()` — build a full plan on the worker thread so
  pre-warming never blocks the GUI loop.
- `turn_started` / `turn_finished`, `approval_needed` / `approval_cleared`,
  `token_usage`, `error`, `message_count`, `compaction_ready`, `config_updated`
  lifecycle signals.
- Persistence: the worker writes its own chat JSON (atomic, one writer per file),
  including committed skill-update banners under `context_banners`.
- Skill-update banner lifecycle: `_sync_pending_banner` creates/removes the
  pending card from the exact pending system-message text; `_commit_pending_banners`
  marks it committed at turn start; delete/regenerate prune or shift anchors.

## Steps / Flow

1. `ensure_worker(chat_id, agent, app)` returns an existing worker (if the agent
   matches) or stops the old one, constructs a new `ChatWorker` and starts the
   thread.
2. `run()` loads persisted token counts and banners on the worker thread, creates
   a new asyncio loop, starts `_pump()`, and signals readiness (`_ready`); then
   `loop.run_forever()`.
3. `_pump()` awaits `agent.event_queue` and calls `_handle_event` for each event
   on the worker thread.
4. GUI commands (`start_turn`, `confirm_approval`, `deny_approval`, `cancel_turn`,
   `set_model`, `update_config`, `delete_turn`, `regenerate`,
   `regenerate_from`, `append_message`, `invalidate_cache`, `set_visible`,
   `request_rebuild`, `request_persist`, `stop`) are posted with `_post`, which
   waits for `_ready` then calls `loop.call_soon_threadsafe`.
5. `_handle_event` mirrors the old GUI consume loop: approval events emit
   `approval_needed`; tool results append to a per-turn list; token usage emits
   `token_usage`; then, when the chat is visible, `_render_active` decides between
   a full plan (`plan_ready`) and a throttled stream update (`stream_updated`).
6. `_finalize` flushes the complete final body into any still-pending streaming
   cards, emits a final plan, persists, resets per-turn render state, and
   triggers compaction when the chat exceeds its limit. Each step is guarded so a
   single failure cannot leave a card truncated or the chat stuck busy, and
   `_run_turn` always emits `turn_finished`.

### Finalization guarantees

The live streaming path is throttled and may drop its last tick, so the full
response is guaranteed by finalization, not by the stream:

- `_update_live` never marks throttled-away text as rendered, so a dropped tick
  is re-detected on the next event.
- `_flush_final_body` writes the whole final text into `BODY_HTML` and clears
  `BODY_TAIL_HTML` for the pending thinking/response rows before per-turn state
  is reset, independent of the rebuild.
- `_finalize` emits the finalized plan unconditionally (not only when visible)
  and guards the flush, plan, and persist steps individually.
- `_run_turn` emits `turn_finished` in a `finally` even if `_finalize` raises.

### Skill-update banner lifecycle

`_do_update_config` calls `_sync_pending_banner(result)` after
`Agent.update_skill_config`:

- The body is `result["pending_sys_message"]` (the exact text that `Agent.run`
  will inject as a system message), formatted as a fenced `System Prompt`
  section.
- A pending banner is anchored at `len(agent.messages)` so it renders at the
  bottom of the transcript.
- Toggling the skill off recomputes the pending text to empty, so the pending
  banner is removed. Tool-mode-only changes also produce empty text, so they
  never create a banner.
- `_do_start_turn` calls `_commit_pending_banners` just before `Agent.run`
  injects the system message; committed banners keep their anchor as later
  messages arrive.
- `_do_persist` stores committed banners under `context_banners`; `__init__`
  reloads them via `_load_banners`. `_prune_banners_after_delete` and
  `_prune_banners_after_trim` keep anchors valid after message edits.

## Function Reference

| Signature | Inputs | Output | Flow | Side effects |
|---|---|---|---|---|
| `def __init__(self, chat_id, agent, app)` | chat id, agent, app | `None` | store references; persisted state loads on the worker thread | — |
| `def run(self) -> None` | — | `None` | `_load_stored_state` → new loop → `_pump` → `run_forever` | thread body |
| `def _load_stored_state(self) -> None` | — | `None` | load true token counts and committed banners from the store | runs on the worker thread |
| `def _shutdown_loop(self) -> None` | — | `None` | cancel tasks, close loop | — |
| `async def _pump(self) -> None` | — | `None` | drain `event_queue`, `_handle_event` | — |
| `def _post(self, callback)` | callback | `None` | `call_soon_threadsafe` | GUI→worker |
| `def start_turn(self, message, gen_id)` | text, generation | `None` | post `_do_start_turn` | — |
| `def confirm_approval(self, tool_id)` | id | `None` | post `agent.approve_tool` | unblocks agent |
| `def deny_approval(self, tool_id, reason)` | id, reason | `None` | post `agent.deny_tool` | unblocks agent |
| `def cancel_turn(self)` | — | `None` | post `_do_cancel` | cancels run task |
| `def set_model(self, model)` | config | `None` | post `agent.set_model` | — |
| `def update_config(self, activated, tools, tool_config)` | payloads | `None` | post `_do_update_config` | emits `config_updated`; syncs pending banner |
| `def delete_turn(self, msg_index)` | index | `None` | post `_do_delete_turn` | mutates messages; prunes banner anchors; persists |
| `def regenerate(self, gen_id)` | generation | `None` | post `_do_regenerate` | trims + restarts |
| `def regenerate_from(self, msg_index, gen_id)` | index, generation | `None` | post `_do_regenerate_from` | trims + restarts |
| `def append_message(self, message)` | message | `None` | post append | — |
| `def invalidate_cache(self)` | — | `None` | post `_do_invalidate` | rebuild |
| `def set_visible(self, visible)` | flag | `None` | post `_do_set_visible` | rebuild on show |
| `def request_rebuild(self)` | — | `None` | post `_emit_plan` | — |
| `def request_prewarm_plan(self)` | — | `None` | post `_emit_plan` | builds on the worker thread |
| `def request_persist(self)` | — | `None` | post `_do_persist` | writes store |
| `def stop(self)` | — | `None` | `loop.stop` + `wait` | joins thread |
| `def _handle_event(self, event)` | event | `None` | per-type dispatch + render | emits signals |
| `def _emit_plan(self)` | — | `None` | build plan, emit `plan_ready` | — |
| `async def _run_turn(self, message, gen_id)` | text, generation | `None` | `agent.run` → `_finalize` | always emits `turn_finished` |
| `def _flush_final_body(self)` | — | `None` | write full final text to pending card bodies | emits `stream_updated` |
| `def _finalize(self)` | — | `None` | flush body → final plan → persist → reset → compact | emits signals; each step guarded |
| `def _load_banners(raw) static` | stored list | normalised banners | force `pending=False`, int anchors | — |
| `def _sync_pending_banner(result)` | config result | `None` | replace/remove pending banner from `pending_sys_message` | rebuild if visible |
| `def _commit_pending_banners(self)` | — | `None` | flip `pending=False` at turn start | — |
| `def _prune_banners_after_delete(start, end)` | deleted range | `None` | drop inside range, shift later anchors | mutates banners |
| `def _prune_banners_after_trim(keep_index)` | trim index | `None` | drop banners anchored after the trim point | mutates banners |

## Registry

| Function | Purpose |
|---|---|
| `get_worker(chat_id)` | Return the running worker or `None` |
| `ensure_worker(chat_id, agent, app)` | Get/create/start the worker |
| `remove_worker(chat_id)` | Stop and drop the worker (blocking) |
| `remove_worker_async(chat_id)` | Detach and stop the worker on a background thread (non-blocking) |
| `stop_all_workers()` | Stop every worker (shutdown) |
