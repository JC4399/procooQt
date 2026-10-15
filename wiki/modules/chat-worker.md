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
- `turn_started` / `turn_finished`, `approval_needed` / `approval_cleared`,
  `token_usage`, `error`, `message_count`, `compaction_ready`, `config_updated`
  lifecycle signals.
- Persistence: the worker writes its own chat JSON (atomic, one writer per file).

## Steps / Flow

1. `ensure_worker(chat_id, agent, app)` returns an existing worker (if the agent
   matches) or stops the old one, constructs a new `ChatWorker` and starts the
   thread.
2. `run()` creates a new asyncio loop, starts `_pump()`, and signals readiness
   (`_ready`); then `loop.run_forever()`.
3. `_pump()` awaits `agent.event_queue` and calls `_handle_event` for each event
   on the worker thread.
4. GUI commands (`start_turn`, `confirm_approval`, `deny_approval`, `cancel_turn`,
   `set_model`, `update_config`, `append_banner`, `delete_turn`, `regenerate`,
   `regenerate_from`, `append_message`, `invalidate_cache`, `set_visible`,
   `request_rebuild`, `request_persist`, `stop`) are posted with `_post`, which
   waits for `_ready` then calls `loop.call_soon_threadsafe`.
5. `_handle_event` mirrors the old GUI consume loop: approval events emit
   `approval_needed`; tool results append to a per-turn list; token usage emits
   `token_usage`; then, when the chat is visible, `_render_active` decides between
   a full plan (`plan_ready`) and a throttled stream update (`stream_updated`).
6. `_finalize` emits a final plan, persists, resets per-turn render state, and
   triggers compaction when the chat exceeds its limit.

## Function Reference

| Signature | Inputs | Output | Flow | Side effects |
|---|---|---|---|---|
| `def __init__(self, chat_id, agent, app)` | chat id, agent, app | `None` | load persisted true token counts | — |
| `def run(self) -> None` | — | `None` | new loop → `_pump` → `run_forever` | thread body |
| `def _shutdown_loop(self) -> None` | — | `None` | cancel tasks, close loop | — |
| `async def _pump(self) -> None` | — | `None` | drain `event_queue`, `_handle_event` | — |
| `def _post(self, callback)` | callback | `None` | `call_soon_threadsafe` | GUI→worker |
| `def start_turn(self, message, gen_id)` | text, generation | `None` | post `_do_start_turn` | — |
| `def confirm_approval(self, tool_id)` | id | `None` | post `agent.approve_tool` | unblocks agent |
| `def deny_approval(self, tool_id, reason)` | id, reason | `None` | post `agent.deny_tool` | unblocks agent |
| `def cancel_turn(self)` | — | `None` | post `_do_cancel` | cancels run task |
| `def set_model(self, model)` | config | `None` | post `agent.set_model` | — |
| `def update_config(self, primary, secondary, tools, tool_config)` | payloads | `None` | post `_do_update_config` | emits `config_updated` |
| `def append_banner(self, banner)` | banner | `None` | post `_do_append_banner` | rebuild |
| `def delete_turn(self, msg_index)` | index | `None` | post `_do_delete_turn` | mutates messages; persists |
| `def regenerate(self, gen_id)` | generation | `None` | post `_do_regenerate` | trims + restarts |
| `def regenerate_from(self, msg_index, gen_id)` | index, generation | `None` | post `_do_regenerate_from` | trims + restarts |
| `def append_message(self, message)` | message | `None` | post append | — |
| `def invalidate_cache(self)` | — | `None` | post `_do_invalidate` | rebuild |
| `def set_visible(self, visible)` | flag | `None` | post `_do_set_visible` | rebuild on show |
| `def request_rebuild(self)` | — | `None` | post `_emit_plan` | — |
| `def request_persist(self)` | — | `None` | post `_do_persist` | writes store |
| `def stop(self)` | — | `None` | `loop.stop` + `wait` | joins thread |
| `def _handle_event(self, event)` | event | `None` | per-type dispatch + render | emits signals |
| `def _emit_plan(self)` | — | `None` | build plan, emit `plan_ready` | — |
| `def _finalize(self)` | — | `None` | final plan, persist, reset, compact | emits signals |

## Registry

| Function | Purpose |
|---|---|
| `get_worker(chat_id)` | Return the running worker or `None` |
| `ensure_worker(chat_id, agent, app)` | Get/create/start the worker |
| `remove_worker(chat_id)` | Stop and drop the worker |
| `stop_all_workers()` | Stop every worker (shutdown) |
