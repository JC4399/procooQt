---
name: subagent
description: >
  Delegate work to headless sub-agents. Create one or many independent agents
  with their own prompt, optional model, skills, and tool whitelist, then collect
  their results. Use when a task can be split into independent parts, when a
  cheaper or different model should handle a subtask, when a worker needs only a
  narrow set of tools, or when several investigations should run in parallel.
  Also use whenever the user asks for sub-agents, workers, a delegation system,
  or mass generation of agents — even if they do not name this skill.
---

# Sub-agents

## Purpose

A sub-agent is a separate headless agent that runs one prompt to completion and
returns its final answer. It has its own model, its own skill instructions, and
its own tool set, so you can delegate a subtask without carrying its context or
giving it tools it does not need. Sub-agents are optional: they exist only while
this skill is selected.

Sub-agents are headless. They cannot ask the user for approval, they cannot open
a chat window, and they cannot spawn further sub-agents. Their records are kept
in memory and disappear when the app exits.

## Deliverable

A result for each delegated task: a JSON record with `status`, `text`, `error`,
`tool_calls`, and token counts. A successful run has `status: "done"` and the
answer in `text`. A failed run has `status: "error"` and a readable `error`.

## Methodology

1. **Split only independent work.** A sub-agent is useful when the subtask can
   run without the main conversation. If the work depends on a back-and-forth
   with the user, do it yourself.
2. **Choose the smallest tool set.** Pass only the skills and tools the worker
   needs. Fewer tools means fewer wrong turns and a smaller prompt.
3. **Choose the model deliberately.** Omit `model` to use the configured
   sub-agent default. Pass another configured model name for cheaper or
   stronger workers.
4. **Use the right mode.**
   - `run` — one task, wait for the answer.
   - `spawn` + `wait` — long task, or when you want to do other work first.
   - `spawn_many` — several independent tasks in one call.
   - `status` / `cancel` — inspect or stop jobs.
5. **Read the result before reporting.** If `status` is `error`, either retry
   with a clearer prompt or do the work yourself.

## Tool reference

The tool is `subagent`. Its main arguments are:

| Argument | Meaning |
|---|---|
| `mode` | `run`, `spawn`, `spawn_many`, `wait`, `status`, or `cancel` |
| `prompt` | The task for one sub-agent |
| `model` | Optional configured model name |
| `activated_skills` | Skill paths whose instructions and tools are loaded |
| `tools` | Explicit tool names; empty means all tools from activated skills |
| `tool_modes` | Per-tool overrides, e.g. `{"edit_file": "block"}` |
| `system_prompt` | Optional extra instruction |
| `specs` | List of request objects for `spawn_many` |
| `agent_id` | Target id for `wait`, `status`, or `cancel` |
| `timeout` | Spawn timeout, or maximum wait time |
| `wait` | For `spawn_many`, wait for every job |

Tool modes are `allow` or `block`. `ask` is not available because no user is
present to approve a headless tool call. Selected tools default to `allow`.

## Examples

One task, wait for the answer:

```text
subagent(mode="run", prompt="Summarise the file at C:/work/report.md",
         activated_skills=["basic/basic-ops"], tools=["read_file"])
```

Start a long task and poll later:

```text
subagent(mode="spawn", prompt="Audit the repository and list risky call sites",
         activated_skills=["basic/basic-ops"])
subagent(mode="wait", agent_id="subagent:20261021_143000:1", timeout=1200)
```

Simple batch:

```text
subagent(mode="spawn_many", wait=True, specs=[
  {"prompt": "Summarise chapter 1 of C:/book.txt", "tools": ["read_file"]},
  {"prompt": "Summarise chapter 2 of C:/book.txt", "tools": ["read_file"]}
])
```

For a custom batch, run a Python script with the basic-ops `execute_script`
tool (`mode="python"`). Add this skill's absolute `scripts/` directory to
`sys.path` and import `_client`; then spawn and collect with `asyncio.gather`.

## Limits

- Nested sub-agents are disabled.
- The server caps concurrent runs; extra jobs queue.
- Each run is bounded by its timeout.
- `run` and `wait` block inside a tool call, so they are bounded by the tool
  runner's subprocess limit (about 10 minutes). For longer work use
  `spawn` (or `spawn_many` with `wait=false`) and poll `status`.
- Completed records are ephemeral and capped in memory.

## References

- `references/batch-patterns.md` — write a custom script with `_client.py` to
  spawn many jobs concurrently and collect their results.
