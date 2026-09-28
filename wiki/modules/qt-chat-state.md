# qt.chat_state — ChatState

Source: `src/qt/chat_state.py`

## Purpose

Per-chat mutable UI state for the Procoo Qt UI. Each live chat owns a
`ChatState`, so several chats can generate concurrently across split panels
while the user switches between them. The state holds
[`ChatListModel`](qt-chat-controller.md) row indices and small value objects — it
never holds a QML object.

## Deliverables

- `StreamingCardState` — tracking state for one streaming card
  (thinking or response).
- `ChatState` — per-chat state with a per-turn reset.
- `ChatState.reset_turn()` — resets streaming, tool, token, and
  render-tracking fields.

## `StreamingCardState`

| Field | Type | Description |
|---|---|---|
| `item_index` | `int \| None` | Row index of the card in `ChatListModel`, or `None` |
| `token_count` | `int` | Last rendered token count for the card |
| `markdown` | `IncrementalMarkdown` | Per-card streaming Markdown renderer that reuses the committed prefix HTML across ticks |

### `reset`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def reset(self) -> None` | — | `None` | `item_index = None`; `token_count = 0`; `markdown.reset()` | Clears the card tracking state |

## `ChatState`

| Field | Type | Description |
|---|---|---|
| `chat_id` | `str` | The chat this state belongs to |
| `generation_id` | `int` | Incremented per generation to detect stale tasks |
| `is_busy` | `bool` | Whether a generation is currently running |
| `has_error` | `bool` | Last generation errored or was stopped by the user; drives the red tab dot until the next send |
| `is_loading` | `bool` | Whether the switch-rebuild overlay is showing |
| `active_task` | `asyncio.Task \| None` | The running `Agent.run` task |
| `approval_event` | `asyncio.Event \| None` | Set when the user resolves a pending approval |
| `approval_text` | `str` | Prompt shown in the approval bar |
| `pending_tool_info` | `dict \| None` | The tool call awaiting approval |
| `current_tool_calls` | `list[dict]` | Tool calls collected during the current turn |
| `tool_results` | `list[dict]` | Tool results collected during the current turn |
| `thinking` | `StreamingCardState` | Streaming state for the thinking card |
| `response` | `StreamingCardState` | Streaming state for the response card |
| `context_banners_data` | `list[dict]` | Delta context banners to render |
| `init_banner_displayed` | `bool` | Whether the initial context banner was shown |
| `context_snapshot` | `dict \| None` | Cached context snapshot so live rebuilds never re-read the chat file |
| `item_cache` | `dict[str, dict[int, object]]` | Rendered chat items keyed by identity (content-hash) key; lets a rebuild reuse every unchanged message |
| `true_input_tokens` | `int` | Latest true input token count from `token_usage`; persisted across turns and restored from storage on hydration |
| `true_output_cum` | `int` | Cumulative true output token count for the current run; persisted across turns and restored from storage on hydration |
| `primary_count` | `int` | Primary skills selected for this chat |
| `allow_count` / `ask_count` / `block_count` | `int` | Tool counts per mode |
| `model_name` | `str` | LLM model selected for this chat (empty = config default) |
| `rendered_item_keys` | `list[str]` | Content hashes of the last rendered chat items |
| `tool_call_indices` | `list[int]` | Row indices of rendered tool-call cards |
| `last_rendered_thinking_text` | `str` | Last thinking text pushed to the model |
| `last_rendered_message_text` | `str` | Last response text pushed to the model |
| `last_rendered_tool_calls` | `int` | Last rendered tool-call count |
| `last_rendered_tool_results` | `int` | Last rendered tool-result count |
| `last_rendered_streaming_tc_json` | `str` | Last rendered streaming tool-call JSON |
| `last_tok_counted_thinking` | `str` | Thinking prefix already counted for tokens |
| `last_tok_counted_response` | `str` | Response prefix already counted for tokens |
| `last_content_update_time` | `float` | Monotonic time of the last content-only update |
| `last_rebuild_time` | `float` | Monotonic time of the last structural rebuild |

The `last_rendered_*` and `last_tok_counted_*` caches live in the
sub-dataclass/state they track (per the project style guide) rather than as flat
prefix sprawl on the controller.

### `reset_turn`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def reset_turn(self) -> None` | — | `None` | reset `thinking`/`response` → clear `current_tool_calls`/`tool_results` → clear `pending_tool_info`/`approval_event`/`approval_text` → clear `rendered_item_keys`/`tool_call_indices` → blank all `last_rendered_*` / `last_tok_counted_*` → zero the two timers | Called by [`ChatController._finalize_turn`](qt-chat-controller.md); does **not** touch `chat_id`, `is_busy`, `has_error`, `generation_id`, `true_input_tokens`, `true_output_cum`, `context_banners_data`, `init_banner_displayed`, `context_snapshot`, or `item_cache` |
