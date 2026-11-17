# automation.manager — AutomationManager

Source: `procooQt/src/automation/manager.py` (models in `src/automation/models.py`)

## Purpose

Discovers automations under a `capabilities/automations/` directory and tracks
each one's enable/disable state and last-run timestamp. An **automation** is any
directory (at any depth) that contains an `AUTOMATION.py` file with YAML
frontmatter. Unlike skills, automations are not fed to the LLM; they are programs
the app runs on a schedule or on an external event. See
[automation-runner](automation-runner.md), [automation-scheduler](automation-scheduler.md),
and [automation-server](automation-server.md).

## Deliverables

- `automations: list[AutomationInfo]` discovered from disk.
- `discover_automations()`, `refresh()`.
- Lookups: `get_automation(path)`, `get_event_automations(event)`,
  `scheduled_automations()`.
- State: `is_enabled`, `set_enabled`, `record_run` persisted to
  `storage/automations.json` (atomic writes; missing entries default to enabled).
- `start_watching` / `stop_watching` — debounced `watchdog` watcher (callback
  runs on the watchdog thread; the caller marshals to the UI thread).
- `get_validation_issues()` — errors/warnings collected during discovery.
- Models: `ActivationType`, `AutomationResultKind`, `AutomationInfo`,
  `AutomationResult`.

## Automation directory format

```
capabilities/automations/
  <group>/
    <automation>/        # contains AUTOMATION.py => an automation
      AUTOMATION.py      # YAML frontmatter + async def run(ctx)
      scripts/           # optional; helper .py files
      references/        # optional; supporting documents
```

Automation identity = relative path from `automations_dir` (e.g. `"reports/daily"`).

### `AUTOMATION.py` frontmatter

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Display name |
| `description` | yes | Short description |
| `activation` | yes | `scheduled` or `event` |
| `schedule` | scheduled only | 5-field cron expression (validated with `croniter`) |
| `event` | event only | Event name matched by the HTTP server |
| `activated_skills` | no | Skill paths fed to the automation's headless agent |
| `start_date` | no | First day the automation may fire, `YYYY-MM-DD` |
| `end_date` | no | Last day the automation may fire, `YYYY-MM-DD` |

The date window gates **scheduled** firing only (the
[scheduler](automation-scheduler.md) skips before `start_date` and auto-disables
after `end_date`); event automations ignore it. Malformed dates produce a
`WARNING` and are treated as unset.

The body after the frontmatter is the Python code (plus skill-like comments). It
must define `async def run(ctx)`; see [automation-runner](automation-runner.md).

## Steps / Flow

### Discovery (`discover_automations`)

1. `rglob("AUTOMATION.py")` sorted; the parent directory is the automation.
2. `frontmatter.load` each file; read `name`, `description`, `activation`,
   `schedule`, `event`, and the optional skill lists.
3. Validate: missing `name`/`description`/`activation` → `ERROR` + skip; a
   scheduled automation with a missing/invalid cron → `ERROR` + skip; an event
   automation with no `event` name → `ERROR` + skip; empty code body, a
   `scripts/` directory with no `.py` files, or a malformed `start_date` /
   `end_date` → `WARNING` (malformed dates are treated as unset).
4. Merge persisted `enabled` / `last_run` from `_state`.
5. Append `AutomationInfo`.

### State storage

`storage/automations.json` holds `{"automations": {"<path>": {"enabled": bool,
"last_run": str}}}`. `set_enabled` and `record_run` update the map and rewrite the
file via a temp file + replace.

### Watching (`start_watching`)

`watchdog.Observer` on `automations_dir` (recursive). Events are debounced
(0.5s); the debounced callback runs **on the watchdog thread** and must only emit
a Qt signal (the [automation controller](qt-automation-controller.md) does this).

## Function Reference

### Public

| Function | Signature | Purpose |
|---|---|---|
| `discover_automations` | `() -> list[AutomationInfo]` | scan for `AUTOMATION.py` |
| `refresh` | `() -> None` | clear issues, re-discover |
| `get_automation` | `(path: str) -> AutomationInfo \| None` | lookup by relative path |
| `get_event_automations` | `(event: str) -> list[AutomationInfo]` | event matches (case-insensitive) |
| `scheduled_automations` | `() -> list[AutomationInfo]` | all scheduled automations |
| `get_validation_issues` | `() -> list[ValidationIssue]` | collected issues |
| `is_enabled` | `(path: str) -> bool` | enabled state (default `True`) |
| `set_enabled` | `(path: str, enabled: bool) -> None` | persist + update model |
| `record_run` | `(path: str, timestamp: str) -> None` | persist last-run |
| `start_watching` | `(callback: Callable[[], None]) -> None` | start watcher |
| `stop_watching` | `() -> None` | stop watcher, cancel timer |

### `AutomationManager.__init__`

| | |
|---|---|
| Signature | `def __init__(self, automations_dir: str, storage_dir: str) -> None` |
| Inputs | `automations_dir` — root to scan; `storage_dir` — state file location. |
| Output | `None` |
| Flow | load state → `discover_automations` → index by path → `_print_validation`. |

### Private (key)

| Function | Signature | Purpose |
|---|---|---|
| `_load_automation_info` | `(auto_file, entry, rel_path) -> AutomationInfo \| None` | parse + validate one file |
| `_load_window_dates` | `(metadata, source) -> tuple[str, str]` | normalise `start_date`/`end_date`, warn on malformed |
| `_load_state` / `_save_state` | `() -> dict` / `() -> None` | read/write `automations.json` |
| `_string_list` | `(value) -> list[str]` | coerce frontmatter list |
| `_add_issue` / `_print_validation` | `(...) -> None` | collect/log validation |
| `_schedule_refresh` / `_on_watcher_debounced` | t=0.5s | debounce plumbing |

### Models

| Model | Fields |
|---|---|
| `ActivationType` (`StrEnum`) | `SCHEDULED`, `EVENT` |
| `AutomationResultKind` (`StrEnum`) | `LOG`, `INFO`, `ERROR`, `SILENT` |
| `AutomationInfo` | `name`, `path`, `directory`, `description`, `activation`, `schedule`, `event`, `activated_skills`, `has_scripts`, `has_references`, `enabled`, `last_run`, `start_date`, `end_date` |
| `AutomationResult` | `kind`, `path`, `task`, `message`, `log`, `data`, `timestamp` |

Module-level helper: `parse_iso_date(value: str) -> date | None` — parses
`YYYY-MM-DD`, returning `None` for empty/malformed input (shared by the manager
and the scheduler).

## See also

- [automation-runner](automation-runner.md) — executes `AUTOMATION.py`.
- [automation-scheduler](automation-scheduler.md) — cron firing.
- [automation-server](automation-server.md) — event dispatch.
- [qt-automation-controller](qt-automation-controller.md) — UI + runtime owner.
- [skill-manager](skill-manager.md) — the sibling discovery subsystem.
