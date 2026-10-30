---
name: subagent
description: >
  Delegate work to a headless sub-agent. Run one independent agent with its own
  prompt, optional model, skills, and tool whitelist, then read its answer and
  the path to its full transcript. Use when a cheaper or different model should
  handle a subtask, when a worker needs only a narrow set of tools, or when the
  user asks for a sub-agent or a worker.
---

# Sub-agents

## Purpose

A sub-agent is a separate headless agent that runs one prompt to completion and
returns its final answer. It has its own model, its own skill instructions, and
its own tool set, so you can delegate a subtask without carrying its context or
giving it tools it does not need. Sub-agents are optional: they exist only while
this skill is selected.

Sub-agents are headless. They cannot ask the user for approval, they cannot open
a chat window, and they cannot spawn further sub-agents. Each run writes a
chat-style JSON transcript to the skill's `references/logs/` directory.

## Deliverable

The tool returns only two things:

```text
<final answer>

Log: C:\...\capabilities\skills\basic\subagent\references\logs\subagent_20261021_143000_1.json
```

The log contains the full run: system prompt, user prompt, thinking, responses,
tool calls, tool results, token usage, and metadata. Read it when you need to
audit how the answer was produced or why a run failed.

## Methodology

1. **Split only independent work.** A sub-agent is useful when the subtask can
   run without the main conversation. If the work depends on a back-and-forth
   with the user, do it yourself.
2. **Choose the smallest tool set.** Pass only the skills and tools the worker
   needs. Fewer tools means fewer wrong turns and a smaller prompt.
3. **Choose the model deliberately.** Omit `model` to use the configured
   sub-agent default. Pass another configured model name for cheaper or
   stronger workers.
4. **Wait for the answer.** The call blocks until the sub-agent finishes, so
   keep the prompt self-contained.
5. **Read the result before reporting.** If the result is an error, either retry
   with a clearer prompt or do the work yourself.

## Tool reference

The tool is `subagent`. Its arguments are:

| Argument | Meaning |
|---|---|
| `prompt` | The task for the sub-agent (required) |
| `model` | Optional configured model name |
| `activated_skills` | Skill paths whose instructions and tools are loaded |
| `tools` | Explicit tool names; empty means all tools from activated skills |
| `tool_modes` | Per-tool overrides, e.g. `{"edit_file": "block"}` |
| `system_prompt` | Optional extra instruction |
| `timeout` | Run timeout in seconds; `0` uses the server default |
| `images` | Optional list of data-URL images attached to the first user message (e.g. `["data:image/webp;base64,…"]`). The multimodal model sees each image on its very first reasoning step — no extra `read_file` round-trip needed. Ignored when the resolved model is not multimodal. |

Tool modes are `allow` or `block`. `ask` is not available because no user is
present to approve a headless tool call. Selected tools default to `allow`.

## Example

```text
subagent(prompt="Summarise the file at C:/work/report.md",
         activated_skills=["basic/basic-ops"], tools=["read_file"])
```

## Limits

- Nested sub-agents are disabled.
- The server caps concurrent runs; extra jobs queue.
- Each run is bounded by its timeout.
- The call blocks inside a tool subprocess, so it is bounded by the tool
  runner's subprocess limit (about 10 minutes). Keep `timeout` below that.
- Completed runs are written to `references/logs/`; no in-memory record is kept.
