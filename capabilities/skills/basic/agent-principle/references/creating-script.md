# Creating a Script

## Purpose

A script is a tool the skill calls to do fixed, input-to-output work. Code is
more reliable than improvisation: it computes, transforms, or produces side
effects the same way every time, behind a typed interface the harness can
enforce. Write a script when the work is deterministic, repetitive, or safer in
code.

## Deliverable

A Python file under `scripts/` that follows the contract below: an `async def
run(...) -> str` with a docstring and typed parameters, returning clean string or
JSON output.

## Methodology

1. Write the `run()` function with typed parameters and a docstring whose first
   paragraph is the tool description and whose `Args:` section documents each
   parameter.
2. Return clean output: structured data as JSON, plain data as a plain string.
3. Catch exceptions and return a readable error, never a raw traceback.
4. Add the `if __name__ == "__main__":` block that reads JSON from stdin and prints
   the result.
5. Make it idempotent: repeated calls must not double-charge or corrupt state.

## Contract

An agent harness is the controlled environment that mediates between the model
and the outside world. It registers tools, routes the agent's calls, and
captures output. This means:

- **SKILL.md is the soul and skeleton.** It says what to do and why, in prose
  the agent reads and reasons over.
- **Scripts are static input-to-output machines.** They hold no knowledge, only
  action. The agent calls them to compute, transform, or produce side effects,
  and the script's typed interface is the safety boundary.

### Safety and Reliability Rules

Every tool script under `scripts/` must follow these rules.

| Rule | Why it matters |
|---|---|
| **Strict typed inputs + `Args:` docstring** | Type annotations and the `Args:` section of the `run()` docstring are parsed at runtime to build the tool's JSON Schema. Missing types default to `string`; missing descriptions leave the agent guessing. |
| **Detailed docstring** | The first paragraph of `run()`'s docstring (up to a blank line or `Args:`) becomes the tool description the agent reads to decide whether to call it. |
| **Clean string/JSON output** | The harness captures stdout as text. No debug prints, raw objects, or binary blobs. Return structured data as JSON, plain data as a string. |
| **No `input()` or prompts** | Agents run asynchronously; blocking on stdin hangs the harness. All inputs come through parameters. |
| **Graceful error handling** | Never crash with a raw traceback. Catch exceptions and return a readable error (preferably `{"error": "..."}`). |
| **Idempotent and safe to re-call** | Agents may retry or loop. Destructive actions need guards; repeated calls must not double-charge or corrupt state. |
| **Side effects via file paths** | If the script generates a file, save it to disk and return the path. Never return binary content or in-memory objects. |

### Canonical Template

```python
"""One-line description of the tool."""

import asyncio
import json
import sys
import traceback

async def run(param: str, option: int = 0) -> str:
    """First paragraph is the tool description used by the agent for discovery.

    Additional paragraphs before ``Args:`` provide extra context for the
    agent — they are read but not used as the tool description.

    Args:
        param: Description of what this parameter does. Appears in the
            agent's tool schema as the per-param description.
        option: Description of what this optional parameter controls.
    """
    try:
        # implementation ...
        return "result string"
    except Exception:
        return json.dumps({"error": traceback.format_exc()})

if __name__ == "__main__":
    args = json.loads(sys.stdin.read())
    result = asyncio.run(run(**args))
    print(result)
```

### Requirements

These 8 rules determine whether a tool is discovered and usable.

1. File in `<skill>/scripts/`, ends with `.py`, no `_` prefix.
2. Module must be importable (no syntax errors, missing imports).
3. Must define `async def run(...) -> str:` with a **non-empty docstring**.
4. Every `run` parameter must have a type annotation.
5. `run` must have `-> str` return annotation.
6. `run` must return a string.
7. Must have `if __name__ == "__main__":` block reading JSON from stdin, calling
   `asyncio.run(run(**args))`, printing the result.
8. The docstring **must** include an `Args:` section documenting each parameter.

### Auto-Inferred Tool Schemas

Tool parameter schemas are built automatically at runtime from the `run()`
function's type annotations and docstring. There is no manual `scripts.json` to
maintain.

For `async def run(param: str, option: int = 0) -> str`, each schema field comes
from a fixed source:

| Schema field | Source |
|---|---|
| `description` | First paragraph of the docstring (up to blank line or `Args:`) |
| `parameters.properties.<name>.type` | Python annotation mapped to JSON Schema |
| `parameters.properties.<name>.description` | `Args:` section: param name matched to its description |
| `parameters.required` | Parameters **without** a default value |

Type mapping:

| Python annotation | JSON Schema type |
|---|---|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `list[str]` | `"array"` (items: `{type: "string"}`) |
| `list` | `"array"` (items: `{type: "string"}`) |
| `dict` | `"object"` |
| `str \| None` / `Optional[str]` | `"string"` (excluded from `required`) |
| Unknown / unannotated | `"string"` |

The canonical template above yields this schema:

```json
{
  "description": "First paragraph is the tool description used by the agent for discovery.",
  "parameters": {
    "type": "object",
    "properties": {
      "param": {
        "type": "string",
        "description": "Description of what this parameter does. Appears in the agent's tool schema as the per-param description."
      },
      "option": {
        "type": "integer",
        "description": "Description of what this optional parameter controls."
      }
    },
    "required": ["param"]
  }
}
```

If no `run()` function is found, or parsing fails, the tool receives an empty
schema (`{"description": "", "parameters": {"type": "object", "properties": {},
"required": []}}`) and a warning is logged.

Default execution timeout is 60 seconds. To override, add a `timeout` parameter
to `run()` with an integer default (e.g. `timeout: int = 120`).

### Standalone Utilities

Only files following the canonical template are discovered as tools. Scripts
using alternative interfaces (`argparse`, `sync def main`, no `async def run`)
are silently skipped. The agent never sees them and cannot call them. If you
need a utility, wrap it with an `async def run(...)` that delegates to it, or
place it outside `scripts/` and invoke it from your `run` function.
