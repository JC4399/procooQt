# subagent — headless sub-agent service

Sources: `src/subagent/models.py`, `src/subagent/manager.py`, `src/subagent/server.py`, `src/subagent/log.py`

## Purpose

Runs one independent, headless agent on behalf of a tool script. The main agent
invokes the optional `subagent` skill tool, which calls a localhost HTTP server;
the server validates the request, builds a temporary [`Agent`](chat-agent.md)
through [`ChatManager`](chat-manager.md), runs one prompt to completion, writes a
chat-style JSON transcript, and returns only the answer plus the transcript path.

This exists because tool scripts are subprocesses and cannot reach
`chat_manager` directly. Sub-agents are headless: they cannot request user
approval, cannot open a chat window, and cannot spawn further sub-agents.

## Deliverables

- `SubAgentSpec` / `SubAgentRecord` / `SubAgentStatus` pydantic models.
- `SubAgentManager` — validation, model/skill/tool resolution, concurrency
  capping, timeout handling, and transcript writing.
- `SubAgentLogWriter` — atomic chat-style JSON logs in
  `capabilities/skills/basic/subagent/references/logs/`.
- `SubAgentServer` — `/health` and `/subagents/run` with the same API-key scheme
  as the automation and control servers.
- Errors as [`SubAgentError`](util-error.md) with UI-visible `brief` and
  log-visible `detail`.

## Steps / Flow

### Run (`SubAgentManager.run`)

1. Reject an empty prompt and a non-empty `parent_id` (nesting disabled).
2. Resolve the model: `spec.model` → `subagent.default_model` → `llm_model_name`;
   reject names not present in `llm_models`.
3. De-duplicate and validate `activated_skills`.
4. Resolve tools:
   - explicit `spec.tools` → `SkillManager.load_tool_functions_by_name`;
   - otherwise tools from `activated_skills`.
5. Validate each selected tool mode (`allow` or `block`; `ask` is unavailable).
6. Create a queued record and call `_execute`, which runs behind the concurrency
   semaphore and builds the temporary `Agent` with
   `tool_env={"PROCOO_SUBAGENT_DEPTH": "1", "PROCOO_SUBAGENT_ID": id}` and the
   app's storage media directory.

### Execute (`SubAgentManager._execute`)

1. Acquire the semaphore.
2. Build the temporary `Agent`.
3. Set `running` and call `asyncio.wait_for(_consume(...), timeout)`.
4. `_consume` runs `agent.run(prompt)` and drains `agent.event_queue`, keeping
   the latest `error` brief.
5. Store the last assistant text, token counters, and terminal status.
6. Write the transcript from the live `agent.messages`.
7. Always remove the temporary chat.

### Log (`SubAgentLogWriter.write`)

The log filename is `subagent_<YYYYmmdd_HHMMSS>_<counter>.json`. Its payload
matches the main chat files in `storage/chats/`:

| Field | Meaning |
|---|---|
| `id` | Sub-agent id |
| `skills_config` | `{"activated": [...], "tools": {...}}` |
| `messages` | Full `agent.messages` history (system prompt, thinking, responses, tool calls/results) |
| `session` | `"subagent"` |
| `created_at` / `updated_at` | Start and finish timestamps |
| `message_count` | Number of captured messages |
| `model_name` | Resolved model |
| `true_input_tokens` / `true_output_cum` | Token counters |
| `status` / `error` | Terminal status and error brief |
| `spec` | Original request |

Writes are atomic (temp file + replace). A log failure does not fail the run; the
record then has an empty `log_path`.

### HTTP (`SubAgentServer`)

| Method | Path | Behaviour |
|---|---|---|
| `POST` | `/subagents/run` | Run one sub-agent and block until it finishes |
| `GET` | `/health` | `{"status": "ok"}` |

`POST /subagents/run` returns `{"text": str, "error": str, "log_path": str}`.
Authentication uses `Authorization: Bearer <key>` or `X-Api-Key`; an empty key
list disables it. The server binds `127.0.0.1` by default.

## Limits

- `subagent.max_concurrent` caps simultaneous runs; extra jobs queue.
- Per-run timeout from `spec.timeout`, clamped to `subagent.max_timeout`.
- The tool call is bounded by the tool runner's subprocess limit (about
  10 minutes); keep `timeout` below that.
- Nesting is blocked in three places: the tool script checks
  `PROCOO_SUBAGENT_DEPTH`, the manager rejects `parent_id`, and sub-agent tool
  subprocesses inherit the depth variable. The manager also strips the
  `subagent` skill from child requests.

## Function Reference

### Models

| Class | Fields | Notes |
|---|---|---|
| `SubAgentStatus` | `QUEUED`, `RUNNING`, `DONE`, `ERROR`, `CANCELLED` | Lifecycle state |
| `SubAgentSpec` | `prompt`, `model`, `activated_skills`, `tools`, `tool_modes`, `system_prompt`, `timeout`, `parent_id` | Request body |
| `SubAgentRecord` | `id`, `status`, `spec`, `model_name`, `activated_skills`, `tool_config`, `created_at`, `finished_at`, `text`, `error`, `tokens`, `log_path` | Run result |

### Manager

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp) -> None` | backend app | `None` | store app | — |
| `async def run(self, spec: SubAgentSpec) -> SubAgentRecord` | request | terminal record | validate → resolve → `_execute` | `SubAgentError`; creates/removes a temporary chat; writes a log |
| `_validate_spec` / `_resolve_model` / `_validate_skills` | request | `None` / `str` | validation and model resolution | `SubAgentError` |
| `_resolve_tools` / `_resolve_timeout` | request | tool defs/config; timeout | resolution | `SubAgentError` |
| `async def _execute(...)` | record + resolved config | `None` | acquire semaphore → build → run → log → cleanup | Mutates record |
| `async def _run_record(...)` | record + agent | `None` | timeout → consume → finish | Mutates record |
| `async def _consume(...)` | agent + record | error brief | run agent; drain events | — |
| `_last_assistant_text` | agent | `str` | last assistant text | — |
| `_read_tokens` | agent | `dict` | input/output token counters | — |
| `async def _write_log(...)` | record + agent | `None` | off-thread atomic write | Sets `log_path` |
| `_log_writer` | — | `SubAgentLogWriter` | locate skill `references/logs` | — |
| `_finish` / `_new_id` | record / — | `None` / id | terminal state; unique id | Mutates record |

### Log writer

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, log_dir: str \| Path) -> None` | log directory | `None` | store path | — |
| `def write(self, record: SubAgentRecord, messages: list[dict]) -> str` | terminal record + history | absolute path | mkdir → build payload → temp write → replace | `OSError` |

### Server

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, host, port, api_keys, manager) -> None` | bind + manager | `None` | store refs | — |
| `def start(self) -> None` | — | `None` | schedule `_start` | Starts server task |
| `async def stop(self) -> None` | — | `None` | cleanup runner; cancel task | Releases socket |
| `async def _handle_run(request)` | request | `{text, error, log_path}` / 4xx | parse → `manager.run` | Blocks |
| `_authorized` / `_extract_key` | request | `bool` / `str` | key check | — |

## See also

- [subagent-flow](../flows/subagent-flow.md) — end-to-end sequence.
- [qt-subagent-controller](qt-subagent-controller.md) — server lifecycle.
- [skill-manager](skill-manager.md) — explicit tool-name loading.
- [chat-agent](chat-agent.md) — the ReAct loop reused here.
- `capabilities/skills/basic/subagent/` — optional skill, tool script, and logs.
