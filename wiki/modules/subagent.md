# subagent — headless sub-agent service

Sources: `src/subagent/models.py`, `src/subagent/manager.py`, `src/subagent/server.py`

## Purpose

Runs independent, headless agents on behalf of a tool script. The main agent
invokes the optional `subagent` skill tool, which calls a localhost HTTP server;
the server validates the request, builds a temporary [`Agent`](chat-agent.md)
through [`ChatManager`](chat-manager.md), runs one prompt to completion, and keeps
the result in memory.

This exists because tool scripts are subprocesses and cannot reach
`chat_manager` directly. The HTTP bridge also lets an agent-authored script spawn
many sub-agents concurrently.

Sub-agents are headless: they cannot request user approval, cannot open a chat
window, and cannot spawn further sub-agents.

## Deliverables

- `SubAgentSpec` / `SubAgentRecord` / `SubAgentStatus` pydantic models.
- `SubAgentManager` — validation, model/skill/tool resolution, scheduling,
  concurrency capping, cancellation, and bounded in-memory records.
- `SubAgentServer` — aiohttp endpoints with the same API-key scheme as the
  automation and control servers.
- Errors as [`SubAgentError`](util-error.md) with UI-visible `brief` and
  log-visible `detail`.

## Steps / Flow

### Create (`SubAgentManager.create`)

1. Reject an empty prompt and a non-empty `parent_id` (nesting disabled).
2. Resolve the model: `spec.model` → `subagent.default_model` → `llm_model_name`;
   reject names not present in `llm_models`.
3. De-duplicate and validate `primary_skills` / `secondary_skills`.
4. Resolve tools:
   - explicit `spec.tools` → `SkillManager.load_tool_functions_by_name`;
   - otherwise tools from `primary_skills`.
5. Validate each selected tool mode (`allow` or `block`; `ask` is unavailable).
6. Store the resolved config, a queued record, and schedule `_execute` behind the
   concurrency semaphore.
7. When the semaphore is acquired, build the temporary `Agent` with
   `chat_manager.create_chat`, passing
   `tool_env={"PROCOO_SUBAGENT_DEPTH": "1", "PROCOO_SUBAGENT_ID": id}`, then run
   it. Building lazily keeps large queues from creating idle agents/clients.

### Execute (`SubAgentManager._execute`)

1. Acquire the semaphore.
2. Build the temporary `Agent` from the stored config.
3. Set `running`.
4. `asyncio.wait_for(_consume(agent, record), timeout)`.
5. `_consume` runs `agent.run(prompt)` and drains `agent.event_queue`,
   recording `tool_call` / `tool_result` events and any `error` brief.
6. Store the last assistant text, token counters, and terminal status.
7. Always remove the prepared config, task, and temporary chat.

### HTTP (`SubAgentServer`)

| Method | Path | Behaviour |
|---|---|---|
| `POST` | `/subagents` | Create one job → `202` queued record |
| `POST` | `/subagents/batch` | Create `{specs, wait}`; `wait` blocks for all |
| `POST` | `/subagents/run` | Create one job and block until terminal |
| `GET` | `/subagents` | List records; optional `?status=` |
| `GET` | `/subagents/{id}` | One record or `404` |
| `POST` | `/subagents/{id}/cancel` | Cancel and return the record |
| `GET` | `/health` | `{"status": "ok"}` |

Authentication uses `Authorization: Bearer <key>` or `X-Api-Key`; an empty key
list disables it. The server binds `127.0.0.1` by default.

## Limits

- `subagent.max_concurrent` caps simultaneous runs; extra jobs queue.
- Per-run timeout from `spec.timeout`, clamped to `subagent.max_timeout`.
- `subagent.max_records` bounds retained records; oldest terminal records are
  dropped first.
- Records are ephemeral and disappear when the app exits.
- Nesting is blocked in three places: the tool script checks
  `PROCOO_SUBAGENT_DEPTH`, the manager rejects `parent_id`, and sub-agent tool
  subprocesses inherit the depth variable. The manager also strips the
  `subagent` skill from child requests.

## Function Reference

### Models

| Class | Fields | Notes |
|---|---|---|
| `SubAgentStatus` | `QUEUED`, `RUNNING`, `DONE`, `ERROR`, `CANCELLED` | `.terminal` property |
| `SubAgentSpec` | `prompt`, `name`, `model`, `primary_skills`, `secondary_skills`, `tools`, `tool_modes`, `system_prompt`, `timeout`, `parent_id` | Request body |
| `SubAgentRecord` | `id`, `status`, `spec`, `model_name`, `tool_config`, `created_at`, `finished_at`, `text`, `error`, `tool_calls`, `tokens` | Response body |

### Manager

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp) -> None` | backend app | `None` | store app; empty records/tasks | — |
| `def create(self, spec: SubAgentSpec) -> SubAgentRecord` | request | queued record | validate → resolve → build agent → schedule | `SubAgentError`; creates a temporary chat |
| `async def run(self, spec: SubAgentSpec) -> SubAgentRecord` | request | terminal record | `create` → `wait` | `SubAgentError` |
| `async def wait(self, agent_id: str) -> SubAgentRecord \| None` | id | terminal record or `None` | await the task | — |
| `async def cancel(self, agent_id: str) -> SubAgentRecord \| None` | id | updated record or `None` | cancel task → await | — |
| `def get(self, agent_id: str) -> SubAgentRecord \| None` | id | record or `None` | — | — |
| `def list_records(self) -> list[SubAgentRecord]` | — | all records | insertion order | — |

### Server

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, host, port, api_keys, manager) -> None` | bind + manager | `None` | store refs | — |
| `def start(self) -> None` | — | `None` | schedule `_start` | Starts server task |
| `async def stop(self) -> None` | — | `None` | cleanup runner; cancel task | Releases socket |
| `async def _handle_spawn(request)` | request | `202` record / 4xx | parse → `manager.create` | Creates a job |
| `async def _handle_spawn_batch(request)` | request | records / 4xx | parse `specs` → create all → optional wait | Creates jobs |
| `async def _handle_run(request)` | request | terminal record / 4xx | parse → `manager.run` | Blocks |
| `async def _handle_get(request)` | request | record / 404 | lookup | — |
| `async def _handle_list(request)` | request | records / 400 | optional status filter | — |
| `async def _handle_cancel(request)` | request | record / 404 | `manager.cancel` | Cancels a job |
| `_authorized` / `_extract_key` | request | `bool` / `str` | key check | — |

## See also

- [subagent-flow](../flows/subagent-flow.md) — end-to-end sequence.
- [qt-subagent-controller](qt-subagent-controller.md) — server lifecycle.
- [skill-manager](skill-manager.md) — explicit tool-name loading.
- [chat-agent](chat-agent.md) — the ReAct loop reused here.
- `capabilities/skills/basic/subagent/` — optional skill and tool scripts.
