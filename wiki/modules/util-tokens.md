# util.tokens — token estimation & tracking

Source: `procooQt/src/util/tokens/counter.py`, `procooQt/src/util/tokens/tracker.py`

## Purpose

Token estimation for context budgeting and UI display:

- `counter.py` — word-count based estimation of plain text and OpenAI-style
  message content (no external tokenizer).
- `tracker.py` — per-session tracker that caches the system-prompt count and
  computes session token/byte totals, with offloaded (async) variants.

## Deliverables

- `count_tokens(text)`, `count_content_tokens(content)` (handles str / list-of-parts).
- `SessionTokenTracker` with `sys_prompt_tokens`, `compute_total(messages)`,
  `compute_bytes(messages)`, and async `compute_total_async` / `compute_bytes_async`.

## counter.py — Function Reference

### `count_tokens`

| | |
|---|---|
| Signature | `def count_tokens(text: str) -> int` |
| Inputs | `text` — plain text. |
| Output | estimated token count: `ceil(words / WORDS_PER_TOKEN)`. |

### `count_content_tokens`

| | |
|---|---|
| Signature | `def count_content_tokens(content: Any) -> int` |
| Inputs | `content` — `str` or list of content parts. |
| Output | total estimated tokens. |
| Flow | `str` counts words; list parts count `text` parts and attribute a flat `IMAGE_TOKEN_ESTIMATE` per `image_url` part. |

## tracker.py — Function Reference

### `SessionTokenTracker`

| | |
|---|---|
| Attributes | `sys_prompt_tokens` (`int`) — cached system-prompt estimate. |

### `SessionTokenTracker.__init__`

| | |
|---|---|
| Signature | `def __init__(self, sys_prompt: str) -> None` |
| Inputs | `sys_prompt` — system prompt string. |
| Output | `None` |
| Side effects | caches `sys_prompt_tokens`. |

### `update_sys_prompt`

| | |
|---|---|
| Signature | `def update_sys_prompt(self, sys_prompt: str) -> None` |
| Inputs | `sys_prompt` — new system prompt. |
| Output | `None` (recaches count). |

### `compute_total`

| | |
|---|---|
| Signature | `def compute_total(self, messages: list[dict[str, Any]]) -> int` |
| Inputs | `messages` — OpenAI-compatible message list. |
| Output | estimated total tokens = sys prompt + per-message content + tool_call name/arguments. |

### `compute_bytes`

| | |
|---|---|
| Signature | `def compute_bytes(self, messages: list[dict[str, Any]]) -> int` |
| Inputs | `messages` — OpenAI-compatible message list. |
| Output | UTF-8 byte size of the JSON-serialized message list. |

### `compute_total_async` / `compute_bytes_async`

Offloaded (`asyncio.to_thread`) variants of `compute_total` / `compute_bytes`
so the UI event loop never blocks.
