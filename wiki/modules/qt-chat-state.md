# qt.chat_state — per-chat GUI state

Source: `src/qt/chat_state.py`

## Purpose

Holds the small set of values the GUI thread needs per chat: busy/error/loading
flags, the pending approval, true token counts, the current message count, and
the config counts. It holds **no** agent, message list, render cache, or
`asyncio` primitive — those live on the chat's
[`ChatWorker`](chat-worker.md) thread. Keeping it GUI-only removes the old
thread-affinity hazards (`active_task`, `approval_event`, `IncrementalMarkdown`).

Related: [`qt-session-controller`](qt-session-controller.md), [`qt-chat-controller`](qt-chat-controller.md), [`chat-worker`](chat-worker.md).

## Deliverables

- `ChatState` dataclass — the per-chat GUI state registry entry.

## Steps / Flow

`SessionController` creates one `ChatState` per chat on demand
(`SessionController.state`). `ChatController` and `SessionController` read and
write its fields on the GUI thread; the worker's signals are the only source of
updates (`token_usage`, `message_count`, `approval_needed`, `approval_cleared`,
`turn_finished`, `error`).

## Attributes

| Attribute | Meaning |
|---|---|
| `chat_id` | The chat this state belongs to |
| `generation_id` | Incremented per generation; detects stale turns |
| `is_busy` | A generation is running |
| `has_error` | Last generation errored or was stopped |
| `is_loading` | A switch rebuild overlay is showing |
| `pending_tool_info` | The tool call awaiting approval |
| `approval_text` | Prompt shown in the approval bar |
| `true_input_tokens` | Latest true input token count from `token_usage` |
| `true_output_cum` | Cumulative true output token count |
| `message_count` | Current message count reported by the worker |
| `activated_count` / `allow_count` / `ask_count` / `block_count` | Config counts |
| `model_name` | Selected model (empty = config default) |

## Function Reference

| Signature | Inputs | Output | Flow / side effects |
|---|---|---|---|
| `def reset_turn(self) -> None` | — | `None` | clear `pending_tool_info` and `approval_text` |
