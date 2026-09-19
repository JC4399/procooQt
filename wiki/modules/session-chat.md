# session.chat — OpenAIChatModel & response types

Source: `procooQt/src/session/chat.py`

## Purpose

OpenAI-compatible chat communication layer: response dataclasses
(`ChatUsage`, `ChatResponse`), JSON-repair helpers, and an
`OpenAIChatModel` client with streaming support.

## Deliverables

- `ChatUsage` (input/output tokens + timing).
- `ChatResponse` (content blocks + id + usage).
- `OpenAIChatModel` — `AsyncClient` wrapper returning either a single
  `ChatResponse` or an `AsyncGenerator[ChatResponse]`.

## Content block format

`ChatResponse.content` is a list of block dicts with a `type` key:

| Type | Fields | Produced from |
|---|---|---|
| `thinking` | `{thinking}` | reasoning deltas |
| `response` | `{response}` | text deltas |
| `tool_use` | `{id, name, input}` | tool-call deltas |

## Steps / Flow

### Streaming (`_parse_stream_response`)

1. Accumulate `thinking`, `text`, and `tool_calls` (by index) across chunks.
2. Capture `usage` from the final chunk (`stream_options.include_usage`).
3. Build content blocks per chunk and `yield ChatResponse`.

### Non-streaming (`_parse_completion_response`)

1. Read `reasoning`/`reasoning_content`, `content`, and `tool_calls`.
2. Repair tool-call arguments with `_json_loads_with_repair`.
3. Return a single `ChatResponse` with usage.

## Function Reference

### `ChatUsage`

| Field | Type | Description |
|---|---|---|
| `input_tokens` | `int` | prompt tokens |
| `output_tokens` | `int` | completion tokens |
| `time` | `float` | wall-clock seconds |

### `ChatResponse`

| Field | Type | Description |
|---|---|---|
| `content` | `list[dict]` | content blocks |
| `id` | `str` | UUID hex (default) |
| `usage` | `ChatUsage \| None` | optional usage |
| `metadata` | `dict \| None` | optional |

### `OpenAIChatModel.__init__`

| | |
|---|---|
| Signature | `def __init__(self, model_name: str, api_key: str \| None = None, stream: bool = True, client_kwargs: dict[str, Any] \| None = None, generate_kwargs: dict[str, Any] \| None = None) -> None` |
| Inputs | `model_name` — model id; `api_key` — optional key (defaults to env); `stream` — streaming mode; `client_kwargs` — extra `AsyncClient` args (e.g. `base_url`); `generate_kwargs` — merged into every request. |
| Output | `None` |
| Side effects | builds `openai.AsyncClient`. |

### `OpenAIChatModel.__call__`

| | |
|---|---|
| Signature | `async def __call__(self, messages, tools=None, tool_choice=None, **kwargs) -> ChatResponse \| AsyncGenerator[ChatResponse]` |
| Inputs | `messages` — OpenAI message dicts; `tools` — tool schemas; `tool_choice` — `auto`/`none`/`required`/function name; `**kwargs` — extra API args. |
| Output | `ChatResponse` (non-stream) or `AsyncGenerator` (stream). |
| Flow | validate messages → build `api_kwargs` → add tools/tool_choice/stream_options → `client.chat.completions.create` → parse. |
| Raises | `ValueError` if messages not a list or missing `role`/`content`. |

### JSON helpers

| Function | Signature | Purpose |
|---|---|---|
| `_json_loads_with_repair` | `(json_str: str) -> dict \| list` | `json_repair` + `json.loads`. |
| `_try_parse_json_dict` | `(json_str: str) -> dict \| list` | try plain parse, fall back to repair. |
