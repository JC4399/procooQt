# Sub-agent flow

How the optional `subagent` skill runs one headless agent, logs its full history,
and returns only the answer plus the transcript path.

Related: [subagent](../modules/subagent.md), [qt-subagent-controller](../modules/qt-subagent-controller.md), [chat-agent](../modules/chat-agent.md), [skill-manager](../modules/skill-manager.md).

## Library layout

```
capabilities/skills/basic/subagent/
  SKILL.md
  scripts/
    subagent.py        # registered tool; also owns the HTTP call
  references/
    logs/              # one JSON transcript per run (.gitkeep keeps the folder)
```

The skill is optional: if it is not selected, the main agent never receives the
`subagent` tool. The server itself starts with the app when
`subagent.enabled: true`.

## Sequence

```
Main agent
  └─ tool: subagent.py (subprocess)
       │  reads PROCOO_SUBAGENT_DEPTH; rejects when > 0
       │  POST /subagents/run
       ▼
SubAgentServer (qasync loop)
  └─ SubAgentManager.run
       ├─ validate model / skills / tools / modes
       ├─ wait for the concurrency semaphore
       ├─ build Agent via chat_manager.create_chat
       │    tool_env: PROCOO_SUBAGENT_DEPTH=1, PROCOO_SUBAGENT_ID=<id>
       ├─ Agent.run(prompt)
       │    └─ ReAct loop + tool subprocesses
       ├─ drain event_queue (keeps the latest error brief)
       ├─ write references/logs/<id>.json from agent.messages
       └─ chat_manager.remove_chat(id)

Tool script
  └─ receives {text, error, log_path}
       └─ prints <answer or error> + "Log: <path>"
```

## Selection semantics

- `activated_skills` — full instructions + all tools from those skills.
- `tools` — explicit tool names across all discovered skills; overrides the
  activated-skill tool set.
- `tool_modes` — `allow` or `block`; `ask` is rejected because no user is present.
- `model` — a configured model name; empty uses the sub-agent default.
- `timeout` — per-run seconds; clamped to the configured maximum.

## Log contract

- Directory: `capabilities/skills/basic/subagent/references/logs/`.
- Filename: `subagent_<YYYYmmdd_HHMMSS>_<counter>.json`.
- Payload keys mirror `storage/chats/*.json`: `id`, `skills_config`, `messages`,
  `session`, `created_at`, `updated_at`, `message_count`, `model_name`,
  `true_input_tokens`, `true_output_cum`.
- Extra keys: `status`, `error`, and `spec`.
- `skills_config` uses `{"activated": [...], "tools": {...}}`.
- `messages` is the agent's full history, including thinking, responses, tool
  calls, and tool results. The tool result only shows the final answer and the
  log path, so the transcript is the place for full metadata.

Writes are atomic (temp file + replace). If writing fails, the run still
succeeds and `log_path` is empty.

## Nesting guard

Nesting is disabled in three layers:

1. `subagent.py` refuses to run when `PROCOO_SUBAGENT_DEPTH > 0`.
2. `SubAgentManager.run` rejects a non-empty `parent_id` and strips the
   `subagent` skill from child skill lists.
3. Sub-agent Agents pass `PROCOO_SUBAGENT_DEPTH=1` to their tool subprocesses.

This is a guardrail, not a sandbox: a sub-agent with `execute_script` could still
hand-craft an HTTP request.

## Result contract

The HTTP response and tool result contain only:

| Field | Meaning |
|---|---|
| `text` | Last assistant response |
| `error` | Error brief when the run failed |
| `log_path` | Absolute transcript path, or an empty string |

The full record (model, activated skills, tool config, token counts, status,
spec) lives in the transcript, not in the tool output.
