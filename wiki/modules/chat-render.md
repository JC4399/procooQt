# chat_render — pure render pipeline

Source: `src/qt/chat_render.py`

## Purpose

Turns a chat's message list into role-keyed chat items (a render plan) and turns
streamed text into in-place row updates. Contains no Qt model or QML access, so
it runs entirely on a per-chat worker thread. The Markdown parser and pygments
formatter it reaches are thread-local, and every card builder returns a plain
dict.

Related: [`chat-worker`](chat-worker.md), [`qt-chat-items`](qt-chat-items.md), [`qt-context-banner`](qt-context-banner.md), [`qt-markdown`](qt-markdown.md).

## Deliverables

- `RenderState` — per-chat render state (item cache, streaming card state, token
  counters, prefix tracking).
- `ChatRenderer.build_plan(...) -> RenderPlan` — full rebuild plan.
- `ChatRenderer.build_stream_update(...) -> list[(row, values)]` — throttled
  in-place streaming body updates.
- `build_context_snapshot(agent) -> dict` — the persisted context snapshot.
- Shared helpers (`assistant_decision`, `delete_bounds`, `accumulate_tokens`, …).

## Steps / Flow

### Build plan (`ChatRenderer.build_plan`)

1. Emit the initial context banner (if a snapshot exists). Skill-update banners
   are interleaved by their `anchor` message index (clamped to the message
   count), so a card stays at the point in the conversation where it was added.
2. Walk the messages; emit user / assistant (thinking, response, tool-call) /
   tool-result rows. Items are memoized by identity key in `RenderState.item_cache`
   so only changed messages re-render.
3. Messages older than `_COLLAPSE_OLDER_THAN` are built collapsed with a `:c` key
   suffix so ageing a message out rebuilds it once.
4. A busy trailing assistant message uses `_build_streaming_assistant_plan`:
   pending thinking/response cards and streaming tool-call rows, whose row indices
   are recorded on the render state for later in-place updates.
5. Emit the `w:pending` waiting scanner while busy with no assistant content yet.

The returned `RenderPlan` owns its `keys` and `items` lists outright. The render
state never aliases them, so a later `reset_turn()` cannot mutate a plan that is
still queued for the GUI thread (keys and items must stay the same length for
`merge_items`).

### Stream update (`ChatRenderer.build_stream_update`)

1. Accumulate token counts for changed thinking/response text.
2. For each changed card, compute `(prefix_html, tail_html)` (thinking via
   `thinking_body_parts`, response via `IncrementalMarkdown.render_parts`) and emit
   a row update carrying only the roles that changed (the tail every tick, the
   frozen prefix only when it grows).
3. Update streaming tool-call argument token text.

## Function Reference

| Signature | Inputs | Output | Flow | Side effects |
|---|---|---|---|---|
| `def content_hash(data)` | str/list | 16-char digest | — | — |
| `def assistant_decision(msg)` | assistant message | decision dict | — | — |
| `def is_waiting_for_assistant(messages, is_busy)` | messages, busy | bool | — | — |
| `def delete_bounds(messages, msg_index)` | messages, index | `(start, end)` | — | — |
| `def accumulate_tokens(text, previous, current)` | text, prefix, count | int | suffix count | — |
| `def build_context_snapshot(agent)` | agent | snapshot dict | reads agent config | — |
| `ChatRenderer.build_plan(messages, snapshot, banners, is_busy)` | inputs | `RenderPlan` | initial banner → anchored banners interleaved with rows → pending | populates `item_cache`, records indices |
| `ChatRenderer.build_stream_update(thinking, content, streaming_tcs, t_changed, c_changed)` | stream inputs | `[(row, values)]` | accumulate → split bodies | mutates render state |
| `ChatRenderer.build_result_replacement(name, content, msg_index)` | tool result | `(item, key)` | — | — |
| `ChatRenderer.invalidate_cache()` / `reset_turn()` | — | `None` | clear cache / streaming state | mutates state |

`PlanBuilder` accumulates keys/items/indices with cache reuse by key.
