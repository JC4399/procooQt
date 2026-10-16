# Agent turn flow

How one user message becomes a streamed assistant response (with tools), now run
on a per-chat worker thread.

Related: [`chat-worker`](../modules/chat-worker.md), [`chat-render`](../modules/chat-render.md), [`chat-agent`](../modules/chat-agent.md), [`qt-chat-controller`](../modules/qt-chat-controller.md), [`chat-llm`](../modules/chat-llm.md).

## Sequence

```
GUI thread                                  Per-chat worker thread (asyncio loop)
──────────                                  ──────────────────────────────────────
user submits (ChatPanel Send / Enter)
  │
ChatPanel.submit → chat._handle_send_for(chat_id, text)
  │  validate non-empty + active chat + not busy
  │  _append_user_message → model.append_item (optimistic row)
  ▼
_launch_generation(chat_id, message)
  │  has_error=False, is_busy=True, generation_id++
  │  _append_waiting_placeholder → model.append_item (w:pending scanner)
  │  _spawn(_start_turn)
  ▼
_start_turn
  │  session._hydrate_chat (build/restore Agent)
  │  attach_worker → ChatWorker            ──command──►  start_turn(message, gen)
  │                                                        │  _do_start_turn
  │                                                        ▼
  │                                                      Agent.run(message)
  │                                                        │  flush _pending_sys_message
  │                                                        │  append user msg
  │                                                        ▼
  │                                                      _run_react_loop ──────┐
  │                                                        │ _reasoning         │ repeat
  │                                                        │  _model(prompt)    │ while
  │                                                        │  stream → _process │ tool
  │                                                        │  emit events       │ blocks
  │                                                        │ _resolve_tool_calls│
  │                                                        ▼                   │
  │                                                      _pump drains event_queue
  │◄── plan_ready / stream_updated / token_usage / ──────┘
  │    approval_needed / turn_finished
  ▼
ChatController apply slots → ChatListModel.diff_update / update_item
  │
_on_turn_finished → clear busy, refresh; (worker) _finalize persists the chat
```

## Per-event handling (worker `_handle_event` → `_render_active`)

1. **thinking / message / tool_call_streaming** — update the render state; the
   live path emits a throttled `stream_updated` (frozen prefix + live tail) or a
   `plan_ready` when the card structure changed.
2. **tool_call** (`ask`) — emit `approval_needed`; the GUI shows the approval bar
   while the agent blocks on its own approval queue (see
   [tool-approval-flow](tool-approval-flow.md)).
3. **tool_result** — append to the per-turn list, emit `approval_cleared`, and
   swap the pending result card (`result_swap`) or rebuild.
4. **token_usage** — emit `token_usage`; the GUI updates the token bar and
   `state.true_input_tokens` / `true_output_cum` (true API counts only).
5. **done / error** — `error` emits `error` and sets `has_error`; then the run
   coroutine finishes and `_finalize` runs.

## Rendering

The worker owns `RenderState` (item cache + incremental Markdown renderers). A
full rebuild produces a content-hash-keyed `RenderPlan` applied with
`diff_update`; content-only streaming emits row updates applied with
`update_item`. The GUI never renders — see [`chat-render`](../modules/chat-render.md).

## Live streaming bodies

Each streaming card body is split into a frozen committed prefix (`BODY_HTML`)
and a live tail (`BODY_TAIL_HTML`): thinking via `thinking_body_parts` (escaped
plain text), the response via `IncrementalMarkdown.render_parts`. Only the tail
is re-laid out in QML each tick; the prefix is re-pushed only when it grows. The
worker throttles content-only updates (0.08 s), and a throttled tick is **not**
marked rendered — the next event still re-detects it. Because each chat renders
on its own thread, one chat's rendering no longer blocks another's.

## Finalization

The live path is throttled and may drop its last tick, so the complete response
is guaranteed at finalize, not by the stream:

- `_flush_final_body` writes the whole final text into `BODY_HTML` (tail cleared)
  for the pending thinking/response rows, before per-turn state is reset.
- `_emit_plan` then emits the finalized plan unconditionally (even when the chat
  is not visible), so `diff_update` replaces the `:pending` row with the full
  finalized body.
- `_finalize` guards the flush, plan, and persist steps independently, and
  `_run_turn` emits `turn_finished` in a `finally`, so a rendering error can
  never leave the card permanently truncated or the chat stuck busy.

The sidebar refresh triggered by a message-count change stays debounced (0.3 s)
on the GUI thread and reads the chat store off-thread.

## Tool execution detail (`Agent.run_tool`)

1. `resolve_tool_python()` + `build_tool_env()` from `src/util/venv.py`.
2. `create_subprocess_exec(...)` on the worker's asyncio loop.
3. `proc.communicate(json.dumps(tool_args))` with the tool's `timeout`.
4. Timeout → kill + message; non-zero exit → error; else stdout (+ stderr).
   Decoded stdout has CR/CRLF normalised to LF.
5. `_parse_tool_media` detects a `_media: true` result → injects images as a
   multimodal user message.

## History editing (delete message / regenerate from a card)

Card headers carry two actions (disabled while busy) that route to worker
commands:

- **Delete message** — `_handle_delete_turn_for` → `worker.delete_turn(msg_index)`.
  `delete_bounds` maps the card to its message object and removes only that
  object plus the minimum needed to keep the history valid. The worker mutates
  `Agent.messages`, resets the render cache, persists, and emits a new plan. A
  chat with no live worker edits the stored record directly.
- **Regenerate from a user card** — `_handle_regenerate_from_for` →
  `worker.regenerate_from(msg_index, gen)`. The worker truncates `messages` to
  before that user message, persists, rebuilds, then starts a fresh turn.

## Compaction handoff

After a turn, the worker checks `Agent.check_limit_exceeded()`. If breached it
summarizes and emits `compaction_ready`; the GUI's
`_create_compacted_chat` writes a new chat seeded with the summary and opens it
in the source chat's panel.
