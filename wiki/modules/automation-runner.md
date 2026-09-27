# automation.runner — AutomationRunner & AutomationContext

Sources: `procooQt/src/automation/runner.py`, `procooQt/src/automation/context.py`

## Purpose

Loads an `AUTOMATION.py`, strips its YAML frontmatter, executes its
`async def run(ctx)` in-process on the qasync loop, and normalises the returned
dict into an `AutomationResult`. The `run` function receives an
`AutomationContext` that bridges scripts to the app's ReAct agent loop so an
automation can ask the LLM without opening a chat panel.

Because the file begins with frontmatter it is **not** importable as a module;
the runner compiles the code body directly.

## Deliverables

- `AutomationRunner(app)` with `run(automation, payload=None) -> AutomationResult`.
- `AutomationContext` with `ask(prompt)`, `payload`, `log()`, `log_text`.
- Captured stdout/stderr plus the context log as the run log.
- Result normalisation: `success` / `info` / `error`; exceptions, bad shapes, and
  bad statuses become `error`.
- `AUTOMATION_TIMEOUT_SEC` (1800s) hard timeout.

## Result contract

`run(ctx)` returns one of:

| Return | Result |
|---|---|
| `{"status": "success", "message": str, "data": any?}` | success |
| `{"status": "info", "message": str, "data": any?}` | info |
| `{"status": "error", "message": str}` | error |
| `None` / `str` | success (message = the string) |
| anything else, unknown status, exception | error |

## Steps / Flow

### `AutomationRunner.run`

1. Off-loop (`asyncio.to_thread`): read `AUTOMATION.py`, `frontmatter.loads(...).content`,
   `compile`, and `exec` into a fresh namespace; fetch `run` (must be a
   coroutine function, else error).
2. Build an `AutomationContext` with the app's config, skill manager, skills dir,
   and the event `payload`.
3. Redirect stdout/stderr into a buffer and `await asyncio.wait_for(run(ctx), 1800)`.
4. On timeout/exception → `error` result with the buffer + traceback; else
   normalise the return value and attach the combined log.

### `AutomationContext.ask`

1. Build a temporary chat id `automation:<path>:<timestamp>`.
2. `chat_manager.create_chat(...)` with the automation's `primary_skills` /
   `secondary_skills`, the default LLM, the base system prompt, and all tools
   forced to `allow` (there is no user to approve).
3. `asyncio.ensure_future(agent.run(prompt))`; drain `agent.event_queue`,
   logging `tool_call`/`tool_result` and capturing `error` briefs.
4. Remove the chat and return the last non-empty assistant message. Raise
   `AutomationError` on agent error or no text.

## Function Reference

### `AutomationRunner`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp) -> None` | `app` | `None` | store `app` | — |
| `async def run(self, automation: AutomationInfo, payload: dict \| None = None) -> AutomationResult` | automation; optional event payload | normalised result | compile → context → redirect + wait_for → combine log | Never raises; timeout/exception → `error` |
| `def _compile_run_function(self, automation) -> Callable` | automation | `run` callable | read + strip frontmatter → `compile` → `exec` | Raises `RuntimeError` when no async `run` |
| `_normalize(raw) static -> tuple[kind, message, data]` | return value | kind/message/data | shape + status validation | invalid → `error` |
| `_error_result(...)` / `_combine_log(...)` | — | `AutomationResult` / `str` | build error; join stdout + ctx log + extra | — |

### `AutomationContext`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, automation, config, skill_manager, skills_dir, payload=None) -> None` | automation; config; skill manager; skills dir; event payload | `None` | store refs; empty log | — |
| `def log(self, message: str) -> None` | message | `None` | append a log line | — |
| `log_text` (property) | — | `str` | newline-joined log lines | — |
| `async def ask(self, prompt: str) -> str` | prompt | assistant reply | temporary agent turn | Raises `AutomationError` |
| `async def _consume_agent(self, agent, prompt) -> str` | agent; prompt | reply text | run + drain queue | Raises `AutomationError` |

## See also

- [automation-manager](automation-manager.md) — discovery and metadata.
- [automation-scheduler](automation-scheduler.md) / [automation-server](automation-server.md) — callers.
- [chat-agent](../modules/chat-agent.md) — the ReAct loop reused via `chat_manager`.
- [util-error](util-error.md) — `AutomationError`.
