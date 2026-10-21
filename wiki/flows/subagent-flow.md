# Sub-agent flow

How the optional `subagent` skill creates a headless agent, runs it, and returns
its result — including the batch path used for mass production.

Related: [subagent](../modules/subagent.md), [qt-subagent-controller](../modules/qt-subagent-controller.md), [chat-agent](../modules/chat-agent.md), [skill-manager](../modules/skill-manager.md).

## Library layout

```
capabilities/skills/basic/subagent/
  SKILL.md
  scripts/
    subagent.py        # registered tool (mode dispatch)
    _client.py         # shared HTTP client; not a registered tool
  references/
    batch-patterns.md
```

The skill is optional: if it is not selected, the main agent never receives the
`subagent` tool. The server itself starts with the app when
`subagent.enabled: true`.

## Sequence

```
Main agent
  └─ tool: subagent.py (subprocess)
       │  reads PROCOO_SUBAGENT_DEPTH; rejects when > 0
       │  POST /subagents (or /batch, /run)
       ▼
SubAgentServer (qasync loop)
  └─ SubAgentManager.create
       ├─ validate model / skills / tools / modes
       ├─ store resolved config + queued record
       └─ schedule _execute behind the semaphore
              │
              ├─ build Agent via chat_manager.create_chat
              │    tool_env: PROCOO_SUBAGENT_DEPTH=1, PROCOO_SUBAGENT_ID=<id>
              ├─ Agent.run(prompt)
              │    └─ ReAct loop + tool subprocesses
              ├─ drain event_queue (tool_call/tool_result/error)
              ├─ store text, tokens, terminal status
              └─ chat_manager.remove_chat(id)

Tool script (spawn + wait, or spawn_many)
  └─ GET /subagents/{id} until terminal
       └─ returns JSON record to the main agent
```

## Modes

| Mode | Calls | Use |
|---|---|---|
| `run` | `POST /subagents/run` | One task, block for the answer |
| `spawn` | `POST /subagents` | Long task; poll later |
| `spawn_many` | `POST /subagents/batch` | Several independent tasks |
| `wait` | `GET /subagents/{id}` polling | Retrieve a spawned result |
| `status` | `GET /subagents` or `/subagents/{id}` | Inspect jobs |
| `cancel` | `POST /subagents/{id}/cancel` | Stop a job |

`run` and `wait` block inside a tool call, so they are bounded by the tool
runner's subprocess limit. For work longer than that, use `spawn` and poll
`status`.

## Selection semantics

- `activated_skills` — full instructions + all tools from those skills.
- `tools` — explicit tool names across all discovered skills; overrides the
  activated-skill tool set.
- `tool_modes` — `allow` or `block`; `ask` is rejected because no user is present.
- `model` — a configured model name; empty uses the sub-agent default.
- `timeout` — per-run seconds; clamped to the configured maximum.

## Batch / mass production

Two paths:

1. `subagent(mode="spawn_many", specs=[...])` for a simple list of requests.
2. An agent-authored script importing `_client.py` from the skill's `scripts/`
   directory and using `asyncio.gather` over `spawn` / `wait`. The reference at
   `references/batch-patterns.md` is the template.

The tool script is a thin client, so any Python or shell script that can reach
the localhost endpoint can spawn sub-agents.

## Nesting guard

Nesting is disabled in three layers:

1. `subagent.py` refuses to run when `PROCOO_SUBAGENT_DEPTH > 0`.
2. `SubAgentManager.create` rejects a non-empty `parent_id` and strips the
   `subagent` skill from child skill lists.
3. Sub-agent Agents pass `PROCOO_SUBAGENT_DEPTH=1` to their tool subprocesses.

This is a guardrail, not a sandbox: a sub-agent with `execute_script` could still
hand-craft an HTTP request.

## Result contract

A record has:

| Field | Meaning |
|---|---|
| `status` | `queued`, `running`, `done`, `error`, or `cancelled` |
| `text` | Last assistant response (success) |
| `error` | Error brief (failure) |
| `tool_calls` | Observed tool calls with modes and error flags |
| `tokens` | `{"input": int, "output": int}` |
| `model_name` | Resolved model |
| `tool_config` | Resolved per-tool modes |
| `spec` | Original request |

Records are in memory only and capped by `subagent.max_records`.
