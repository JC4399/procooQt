# Agent turn flow

How one user message becomes a streamed assistant response (with tools).

Related: [`chat-agent`](../modules/chat-agent.md), [`chat-llm`](../modules/chat-llm.md), [`qt-chat-controller`](../modules/qt-chat-controller.md).

## Sequence

```
user types / presses Enter (ChatPanel.qml)
   │
   ▼
ChatPanel.submit → chat._handle_send_for(chat_id, text)   [ChatController @Slot]
   │  validate non-empty + active chat + not busy
   │  _append_user_message(chat_id, text) → model.append_item (optimistic row)
   ▼
_launch_generation(chat_id, message)
   │  state.has_error=False, is_busy=True, generation_id++
   │  _append_waiting_placeholder → model.append_item (w:pending scanner)
   │  _spawn(_run_chat_loop)
   ▼
_run_chat_loop(message, gen_id, chat_id)
   │  _hydrate_phase → session._hydrate_chat (build/restore Agent)
   │  task = ensure_future(chat.run(message))
   │  await sleep(0) → rebuild (reconciles; scanner already visible)
   │  await _consume_events(chat, chat_id, state, task)
   ▼
Agent.run(message)  [src/chat/agent.py]
   │  flush _pending_sys_message (skill delta) as system msg
   │  append user msg
   ▼
_run_react_loop ──────────────┐
   │                          │ repeat while tool_blocks
   ▼                          │
_reasoning                    │
   │  _build_prompt(messages)  │
   │  _model(prompt, tools)    │
   │  stream chunks → _process_blocks
   │     thinking → emit "thinking"
   │     response → emit "message"
   │     tool_use → collect + emit "tool_call_streaming"
   │  emit "token_usage"
   ▼ returns tool_blocks
   │
   ├─ empty? ──────────> emit "done" -> END
   │
   ▼
_resolve_tool_calls ───────────┘
   1. register tool_calls + emit "tool_call"
   2. decide: block→deny / allow→approve / ask→await approval
   3. execute: run_tool (subprocess) + _record_tool_result
      - emit "tool_result"
      - media? → _inject_media_user_message
```

## Step-by-step (per event, consumed by `ChatController._consume_events`)

1. **thinking / message / tool_call_streaming** — no structural action; the
   loop later calls `_update_live_assistant` for throttled token-count updates.
2. **tool_call** (ask mode) — `_handle_approval` blocks on
   `state.approval_event` until approve/deny/stop.
3. **tool_result** — appended to `state.tool_results`; `_swap_pending_result_card`
   replaces the pending card in place.
4. **token_usage** — `state.true_input_tokens` / `state.true_output_cum`
   update (true API counts only, no estimate); the panel's `ConfigTokenBar`
   (via `ChatPanelModel`) refreshes. The counts persist across turns.
5. **done / error** — break out of the loop; an `error` also sets
   `state.has_error` so the chat's tab dot shows red until the next send.
6. `finally: _finalize_turn` — rebuild the chat display, save the chat,
   reset per-turn tracking, and update the Send/Stop buttons.

`_launch_generation` appends the pre-response scanner immediately: right after
setting `state.is_busy`, it calls `_append_waiting_placeholder`, which appends a
`KIND_WAITING` row keyed `w:pending` in the same frame as the user card — before
`_hydrate_phase` (Agent construction / skill loading) and before the network
request. So a headerless grey `KnightRiderSpinner` (`WaitingCard.qml`) is visible
for the whole wait, whether that is hydration, model prefill, a slow network, or
a pending failure; it does not wait for an HTTP response. `_run_chat_loop` later
rebuilds once after `await asyncio.sleep(0)` (long enough for `Agent.run` to
append the user message), which reconciles because
`_build_plan` emits the matching `u:<hash>` + `w:pending`
while waiting. The first `thinking`/`message`/`tool_call_streaming` card diverges
at that index and replaces the scanner via `ChatListModel.diff_update`.

The drain loop uses `await asyncio.wait_for(chat.event_queue.get(), 0.1)`
so it also exits once the `Agent.run` task is done and the queue is empty.

## Live rendering (`_render_active_event` / `_update_live_assistant`)

Structural changes (tool calls/results appearing, streaming tool calls first
appearing) rebuild immediately; the rebuild reuses memoized items for every
unchanged message, so only the changed trailing message is re-rendered.
Content-only streaming updates are throttled (`_STREAM_UPDATE_INTERVAL`, 0.08 s)
and applied in place via `ChatListModel.update_item`: thinking is written as
escaped plain text, and the response is rendered through a per-card
`IncrementalMarkdown` on a worker thread (`asyncio.to_thread`) so only the
trailing Markdown block is re-rendered and the parse/highlight never blocks the
GUI thread. A full rebuild computes content-hash render keys and calls
`ChatListModel.diff_update`, which removes and re-inserts rows from the first
divergence only.

The sidebar refresh triggered by a message-count change is debounced (0.3 s) and
its disk scan runs off the GUI thread via
`SessionController.refresh_model_async`.

## Tool execution detail (`Agent.run_tool`)

1. `resolve_tool_python()` + `build_tool_env()` from `src/util/venv.py`.
2. `create_subprocess_exec(tool_python, script_path, stdin/stdout/stderr=PIPE)`.
3. `proc.communicate(json.dumps(tool_args))` with the tool's `timeout`
   (default 600s).
4. Timeout → kill + message; non-zero exit → error message; else stdout
   (+ appended stderr). Decoded stdout has CR/CRLF normalised to LF so stored
   messages and prompts stay clean on Windows.
5. `_parse_tool_media` detects a `_media: true` JSON result → images are
   injected as a multimodal user message (`_inject_media_user_message`).

## History editing (delete turn / regenerate from a card)

Card headers carry two actions (`CardBase.qml`, disabled while the chat is busy)
that edit `chat.messages` and rebuild:

- **Delete turn** — the trash icon on any card routes to
  `ChatController._handle_delete_turn_for(chat_id, msg_index)` →
  `_delete_turn`. `_round_bounds` expands `msg_index` to the whole turn (back to
  the nearest user message, over any injected system messages; forward to the
  next user message), so the prompt, assistant reply, tool calls, and tool
  results are removed together and the history stays LLM-valid. The live
  `Agent.messages` list is mutated in place (the cached item cache is cleared,
  `_current_assistant_msg` reset) or the stored record is rewritten when the chat
  is not hydrated; then `_rebuild_chat_display` + `_refresh_sidebar`.
- **Regenerate from a user card** — the reload icon routes to
  `ChatController._handle_regenerate_from_for(chat_id, msg_index)` →
  `_regenerate_from`: discard `messages[msg_index:]`, persist the prefix, drop
  delta banners, drop the live chat, rebuild, then `_launch_generation` re-sends
  that user message (the same truncate-and-relaunch path as `_regenerate`).

## Compaction handoff

After `_finalize_turn`, if `chat.check_limit_exceeded()` reports a breach,
`ChatController._compact_chat` summarizes the chat
(`Agent.summarize`) and creates a fresh chat seeded with the summary
(`_create_compacted_chat`), then opens it in the source chat's panel.
