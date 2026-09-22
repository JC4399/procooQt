# util.log — colored logging

Source: `procooQt/src/util/log/formatter.py`

## Purpose

One module provides ANSI-colored terminal logging:

- `formatter.py` — a `logging.Formatter` that colors log records by level,
  plus a root-logger setup helper and colored log-line builders for skill /
  tool / preset changes and chat-skills logging.

## Deliverables

- `ColoredFormatter` and `setup_colored_logging(level)`.
- `format_skill_change`, `format_tool_change`, `format_preset_save/load/delete`
  (colored strings for log lines).
- `log_chat_skills`.

## formatter.py — Function Reference

### `ColoredFormatter`

| | |
|---|---|
| Signature | `class ColoredFormatter(logging.Formatter)` |
| Purpose | applies ANSI colors to levelname/name/msg/asctime when stderr is a TTY. |

### `ColoredFormatter.__init__`

| | |
|---|---|
| Signature | `def __init__(self, fmt: str \| None = None, datefmt: str \| None = None) -> None` |
| Inputs | `fmt`, `datefmt` — optional format/date strings. |
| Output | `None` |
| Side effects | sets `_use_colors = sys.stderr.isatty()`. |

### `ColoredFormatter.format`

| | |
|---|---|
| Signature | `def format(self, record: logging.LogRecord) -> str` |
| Inputs | `record` — log record. |
| Output | formatted (optionally colored) string. |

### `setup_colored_logging`

| | |
|---|---|
| Signature | `def setup_colored_logging(level: int = logging.INFO) -> None` |
| Inputs | `level` — root log level. |
| Output | `None` |
| Side effects | clears root handlers, adds a colored `StreamHandler` to stderr. |

### Colored log-line builders

| Function | Signature | Purpose |
|---|---|---|
| `format_skill_change` | `(skill_name, skill_type, value) -> str` | colored skill checkbox line |
| `format_tool_change` | `(full_tool_name, value) -> str` | colored tool radio line |
| `format_preset_save` | `(preset_name, primary, secondary, tools) -> str` | preset save line |
| `format_preset_load` | `(preset_name, primary, secondary, tools) -> str` | preset load line |
| `format_preset_delete` | `(preset_name) -> str` | preset delete line |

### `log_chat_skills`

| | |
|---|---|
| Signature | `def log_chat_skills(primary_skills: list[str], secondary_skills: list[str], tool_defs: list[dict]) -> None` |
| Inputs | `primary_skills`, `secondary_skills` — skill path lists; `tool_defs` — tool defs with `name` + `skill_path`. |
| Output | `None` (prints summary to stderr). |
