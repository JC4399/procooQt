# util.venv — tool interpreter resolution

Source: `procooQt/src/util/venv.py`

## Purpose

Resolves the Python interpreter and environment that tool subprocesses run
under, so `python`/`shell` tool execution always targets the project `.venv`
rather than whichever interpreter launched the app.

## Deliverables

- `resolve_tool_python()` — absolute path to the target interpreter.
- `build_tool_env(python_path, extra_env=None)` — `os.environ` copy with venv
  activated (`PATH` + `VIRTUAL_ENV`) plus optional extra variables.

## Steps / Flow

`resolve_tool_python()`:

1. If already running in a venv (`sys.prefix != sys.base_prefix`), return
   `sys.executable`.
2. Compute project `.venv` interpreter path (`.venv/Scripts/python.exe` on
   Windows, `.venv/bin/python` on Unix).
3. If that file exists, return it (log info).
4. Otherwise warn and fall back to `sys.executable`.

`build_tool_env()`:

1. Determine target interpreter (arg or `resolve_tool_python()`).
2. Copy `os.environ`.
3. If target is a venv (detected via `pyvenv.cfg`), prepend its scripts dir
   to `PATH` and set `VIRTUAL_ENV`.
4. Merge `extra_env` last so callers (e.g. sub-agents) can override values.

## Function Reference

### `resolve_tool_python`

| | |
|---|---|
| Signature | `def resolve_tool_python() -> str` |
| Output | absolute path string to the target interpreter. |

### `build_tool_env`

| | |
|---|---|
| Signature | `def build_tool_env(python_path: str \| None = None, extra_env: dict[str, str] \| None = None) -> dict[str, str]` |
| Inputs | `python_path` — optional interpreter path (defaults to resolved tool Python); `extra_env` — optional variables merged last. |
| Output | `os.environ` copy with venv injected and `extra_env` applied (or an unmodified copy plus `extra_env` if not a venv). |

### Private helpers

| Function | Signature | Purpose |
|---|---|---|
| `_project_root` | `() -> Path` | project root (parent of `src`). |
| `_venv_python_path` | `() -> Path` | project `.venv` interpreter path. |
| `_is_venv_interpreter` | `(python_path: Path) -> bool` | `True` if interpreter sits in a venv (has `pyvenv.cfg`). |
