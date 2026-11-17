# qt.automation_controller — automation page & runtime

Source: `src/qt/automation_controller.py`

## Purpose

Owns the automation subsystem runtime and the automation page model: the list
model behind `AutomationPanel.qml`, the fuzzy search filter, enable/disable
toggles, manual runs (with an in-flight running indicator per card), and the
lifecycle of the cron scheduler and the inbound HTTP event server. Completed runs are emitted as `result_ready` for the
[notification controller](qt-notification-controller.md); the editor is opened
through `edit_automation_requested`.

The `watchdog` callback runs on a background thread and only emits
`files_changed`; the connected slot then refreshes off-loop.

## Deliverables

- `AutomationListModel` (`automation.automation_model`) and the `searchText`
  property.
- `AutomationRunner`, `AutomationScheduler`, `AutomationEventServer` instances.
- Signals: `automations_changed`, `files_changed`, `result_ready`,
  `edit_automation_requested`, `toast_requested`.
- Slots: `start`, search, toggle, edit, run-now, watcher refresh.

Date windows (`start_date` / `end_date` frontmatter) are **read-only display
data**: the model exposes a precomputed `WINDOW_TEXT` role (range +
`pending`/`active`/`expired`), and `AutomationCard.qml` renders it in a
"Window" row hidden when unset. No slots exist for editing it; watchdog
refreshes pick up frontmatter edits automatically.

## Signals & properties

| Signal | Payload | Emitted when |
|---|---|---|
| `automations_changed` | — | The model was rebuilt. |
| `files_changed` | — | Watchdog thread detected a change (queued to GUI). |
| `result_ready` | `object` (`AutomationResult`) | A scheduled/event/manual run finished. |
| `edit_automation_requested` | `str` | Edit requested; payload is the automation path. |
| `toast_requested` | `str, str` | A message + toast level. |

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `automation_model` | `QObject` | `automations_changed` | Automation cards for the panel. |
| `searchText` | `str` | `automations_changed` | Active fuzzy filter. |

## Steps / Flow

### Build (`build`)

Create the model; construct the runner, scheduler (manager + runner +
`_on_result`), and event server (host/port/api keys from `app.config`); connect
`files_changed`; `_rebuild()`.

### Start (`start`)

`manager.start_watching(self._on_files_changed)` (thread → signal),
`scheduler.start()`, `server.start()`.

### Run and refresh

- `_handle_run_now(path)` → `_run_now(path)`: adds the path to `_running`, calls
  `model.set_running(path, True)` (spinner + disabled button), runs
  `runner.run(info)`, records the run, then clears `_running` in a `finally` via
  `model.set_running(path, False)`, and calls `_on_result`.
- `_on_result(result)` emits `result_ready` (except for silent results) and
  rebuilds the list.
- `_rebuild()` passes `_running` into `set_automations`, so in-flight state
  survives the reset.
- Watchdog → `files_changed` → `_handle_files_changed` → `_refresh()`:
  `asyncio.to_thread(manager.refresh)`, `scheduler.notify_changed()`, `_rebuild()`.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app: ProcooApp, parent: QObject \| None = None) -> None` | app; parent | `None` | store app; init task set | — |
| `def build(self) -> None` | — | `None` | model + runner + scheduler + server; connect; rebuild | — |
| `@Slot() def start(self) -> None` | — | `None` | watch + scheduler.start + server.start | Starts watcher/HTTP bind |
| `@Slot(str) def _handle_search_changed(self, text: str) -> None` | text | `None` | store filter; rebuild | Emits `automations_changed` |
| `@Slot(str, bool) def _handle_toggle(self, path: str, enabled: bool) -> None` | path; enabled | `None` | persist; `notify_changed`; rebuild | Writes `automations.json` |
| `@Slot(str) def _handle_edit(self, path: str) -> None` | path | `None` | emit `edit_automation_requested` | — |
| `@Slot(str) def _handle_run_now(self, path: str) -> None` | path | `None` | spawn `_run_now` | Schedules a run |
| `async def _run_now(self, path: str) -> None` | path | `None` | mark running → `runner.run` → `record_run` → clear running → `_on_result` | Updates model `RUNNING`; emits `result_ready`; toasts on unknown path |
| `def _on_result(self, result: AutomationResult) -> None` | result | `None` | emit `result_ready` unless silent; rebuild | — |
| `def _on_files_changed(self) -> None` | — | `None` | emit `files_changed` (watchdog thread) | — |
| `@Slot() def _handle_files_changed(self) -> None` | — | `None` | spawn `_refresh` | — |
| `async def _refresh(self) -> None` | — | `None` | off-loop manager refresh; reschedule; rebuild | Toast on failure |

## See also

- [automation-manager](automation-manager.md) / [automation-scheduler](automation-scheduler.md) / [automation-server](automation-server.md).
- [automation-runner](automation-runner.md).
- [qt-models](qt-models.md) — `AutomationListModel`.
- [qt-ui](qt-ui.md) — composition + context property.
