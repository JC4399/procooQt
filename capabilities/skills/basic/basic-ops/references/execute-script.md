# execute_script

Dispatches on the `mode` parameter (`python`, `shell`, `skill`) — `mode` is
required. Each mode reads its own canonical argument:

| mode | argument |
|---|---|
| `python` | `code` |
| `shell` | `command` |
| `skill` | `script` (absolute path) + `params` (argument object) |

Always put the payload in that top-level argument — never nest
`code`/`command`/`script` inside `params`. If the canonical argument is omitted
the tool falls back to the other payload arguments, so a misnamed argument still
runs. `timeout` — maximum execution time in seconds, default 600.

## Before reaching for this tool

NEVER use `execute_script` (shell or python) for anything the dedicated file
tools do — `read_file`, `edit_file`, `search_dir` are safer and return structured
output. See the DO-NOT-use tables in `SKILL.md`.

## mode=shell

Reserve for: git, npm, pip, docker, pytest, cargo and other build/test/package
commands; curl, wget for network requests; any operation that genuinely requires
a shell interpreter.

When installing Python packages always use `python -m pip install <package>`
rather than bare `pip install <package>`. This installs into the same virtual
environment `execute_script` uses, so packages installed in shell mode are
immediately importable in python mode.

```json
{"mode": "shell", "command": "python -m pip install requests"}
```
Result: packages installed to the correct venv

```json
{"mode": "shell", "command": "git status"}
```
Result: working tree status

```json
{"mode": "shell", "command": "rm -rf /tmp/test/"}
```
Result: "Blocked by safety guard (rm -r / rm -rf (recursive delete)): rm -rf /tmp/test/"

## mode=python

Reserve for: data processing, complex logic, API calls, computation; any task
that genuinely needs a Python runtime.

```json
{"mode": "python", "code": "import json\nprint(json.dumps(sorted([3, 1, 2])))"}
```
Result: "[1, 2, 3]"

## mode=skill — calling another skill's script

Reserve for invoking an on-demand skill's script (a script not registered as a
tool). The script must follow the skill-script contract: read one JSON object
from stdin and call `run(**args)`.

- `script` — absolute path to the skill's `.py` script.
- `params` — JSON object forwarded to the script's `run(**params)`.
- `timeout` — maximum execution time in seconds (default 600).

The harness serialises `params` and pipes it to the script's stdin, exactly as
the tool runtime does — the JSON never passes through a shell.

**NEVER pipe JSON to a skill script through `mode=shell`** (e.g.
`echo '{...}' | python script.py`). PowerShell quoting corrupts nested JSON;
`mode=skill` exists precisely to avoid it.

The output is the script's stdout, returned as-is (not truncated), so a script
that returns a `_media` payload is handled the same way as a registered tool.

```json
{"mode": "skill", "script": "C:/Users/me/capabilities/skills/works/update-todo-list/scripts/format_todo.py", "params": {"file_path": "C:/Users/me/Notes/26 06 Week 3.md"}}
```
Result: the script's stdout, e.g. the JSON summary of the reformatted todo list.
