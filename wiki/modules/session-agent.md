# session.agent — Agent (ReAct loop)

Source: `procooQt/src/session/agent.py`

## Purpose

Unified agent class combining conversation memory, LLM reasoning, subprocess
tool execution, tool-approval workflow, and UI event streaming — no wrapper
layers.

## Deliverables

- `self.messages` — OpenAI-compatible conversation history with `_`-prefixed
  metadata (`reasoning_content` on assistant, `_mode` + `_streaming_tool_calls`
  on tool_calls).
- `event_queue` — `asyncio.Queue` of UI events.
- `run(message_content)` — executes one user turn.
- `approve_tool` / `deny_tool` — release pending approvals.
- `update_skill_config` — hot-swap skills/tools with delta warnings.
- `run_tool` — subprocess tool execution.

## Key attributes

| Attribute | Type | Description |
|---|---|---|
| `session_id` | `str` | unique id |
| `event_queue` | `asyncio.Queue` | UI events |
| `messages` | `list[dict]` | conversation history |
| `primary_skills` / `secondary_skills` | `list[str]` | skill paths |
| `sys_prompt` | `str` | full system prompt |
| `_tools` | `dict[str, dict]` | registered tool defs |
| `_tool_config` | `dict[str, str]` | per-tool mode |
| `_pending_approvals` | `dict[str, asyncio.Queue]` | approval queues |

## Steps / Flow

### `run` (one turn)

1. Reset per-turn API counters.
2. If a pending skill delta exists, append it as a `system` message.
3. Append the user message.
4. `_run_react_loop()`.
5. `refresh_estimated()`; emit `done`.
6. On `CancelledError` → emit `error` (cancelled); on exception → emit `error` with traceback.

### `_run_react_loop`

```
while True:
    tool_blocks = await _reasoning()     # one LLM call, streams events
    if not tool_blocks: return           # model answered with text only
    await _resolve_tool_calls(tool_blocks)
```

### `_resolve_tool_calls` (3-phase)

1. **Register** — build OpenAI `tool_calls`, parse/repair args, strip empty
   optional args, emit `tool_call` events.
2. **Decide** — concurrently `_get_decision`: `block`→deny, `allow`→approve,
   `ask`→await approval.
3. **Execute** — concurrently `run_tool`, recording results; inject media if
   a tool returned `_media: true`.

### `run_tool`

1. Resolve `tool_python` + `build_tool_env`.
2. `create_subprocess_exec(tool_python, script_path, stdin=PIPE, ...)`.
3. `communicate(args_json)` with timeout.
4. On timeout → kill, return timeout message; non-zero exit → error message;
   else stdout (+ stderr appended). Decoded stdout has CR/CRLF normalised to LF.

Full turn detail: [`flows/agent-turn-flow`](../flows/agent-turn-flow.md).

## Function Reference

### `Agent.__init__`

| | |
|---|---|
| Signature | `def __init__(self, session_id, model, primary_skill_contents, secondary_skill_contents, tool_functions, tool_config, skills_dir, system_message="You are a helpful assistant.", sampling_config=None, initial_messages=None, summary_prompt="", session_limits=None) -> None` |
| Inputs | see docstring; `model` = `{model_name, api_key, api_base}`; `tool_config` = per-tool mode; `initial_messages` seeds history; `summary_prompt` = summarization instruction; `session_limits` = `{"max_bytes": int, "max_tokens": int}` (0 disables). |
| Output | `None` |
| Flow | init queue/approvals → build `sys_prompt` from primary/secondary skills → `SessionTokenTracker` → `OpenAIChatModel(stream=True)` → register tools → log skills. |

### `run`

| | |
|---|---|
| Signature | `async def run(self, message_content: str) -> None` |
| Inputs | `message_content` — user text. |
| Output | `None` (streams events). |
| Side effects | appends to `messages`, emits events. |

### `update_skill_config`

| | |
|---|---|
| Signature | `def update_skill_config(self, primary_skill_contents, secondary_skill_contents, tool_functions, tool_config) -> dict` |
| Inputs | new skill contents, tool defs, tool config. |
| Output | `{warnings, added_primary, added_secondary, added_tools}`. |
| Flow | compute removed/demoted → build warnings → accumulate additions into `_pending_sys_message` → add new tools → `set_tool_config`. |

### `run_tool`

| | |
|---|---|
| Signature | `async def run_tool(self, tool_name: str, tool_args: dict \| list) -> str` |
| Inputs | `tool_name` — registered tool name; `tool_args` — JSON args (stdin). |
| Output | stdout string (CR/CRLF normalised to LF), or error/timeout message. |
| Flow | resolve venv → subprocess → `communicate` with timeout → decode + LF-normalise → error handling. |

### `approve_tool` / `deny_tool`

| | |
|---|---|
| Signature | `async def approve_tool(self, tool_call_id: str) -> None` / `async def deny_tool(self, tool_call_id: str, denial_reason: str = "") -> None` |
| Inputs | `tool_call_id`; `denial_reason` optional. |
| Output | `None` (puts `("approve"/"deny", reason)` onto the pending queue). |

### Session compaction

| Method | Signature | Purpose |
|---|---|---|
| `check_limit_exceeded` | `() -> dict \| None` | returns `{"reason", "bytes", "tokens"}` when byte/token limit exceeded, else `None`. |
| `summarize` | `async () -> str` | single non-tool LLM call producing a summary of the history. |
| `_render_messages_for_summary` | `() -> str` | compact role-labelled serialization of `messages`. |

### Key private methods

| Method | Purpose |
|---|---|
| `_run_react_loop` | reasoning ⇄ tool execution |
| `_reasoning` | one LLM call + streaming block processing |
| `_resolve_tool_calls` | register/decide/execute tools |
| `_process_blocks` | emit thinking/message events, write `_streaming_tool_calls` |
| `_record_tool_result` | emit `tool_result`, append `role: tool` message |
| `_build_prompt` | system prompt + history (+ suffix) |
| `_build_tool_schemas` | OpenAI tool schema from `_tools` |
| `_parse_tool_media` | detect `_media` marker in tool output |
| `_inject_media_user_message` | inject image content as user message |
| `_format_secondary_skills_prompt` | secondary-skills prompt section |
| `_strip_empty_optional_args` | drop empty optional params |
