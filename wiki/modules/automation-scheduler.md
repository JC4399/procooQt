# automation.scheduler — AutomationScheduler

Source: `procooQt/src/automation/scheduler.py`

## Purpose

Fires enabled cron-scheduled automations. One asyncio task waits for the nearest
next-run time across all enabled scheduled automations, runs due ones
sequentially through the [runner](automation-runner.md), records their last-run
state, and forwards each result to a callback. It runs on the same qasync loop as
the UI.

Automations may declare an optional `start_date` / `end_date` window
(`YYYY-MM-DD`) in their frontmatter: firing is skipped before the start date,
and enabled automations whose end date has passed are auto-disabled through
`manager.set_enabled`.

## Deliverables

- `AutomationScheduler(manager, runner, on_result)`.
- `start()` / `stop()` lifecycle; `notify_changed()` to reschedule after edits.
- `run_now(automation) -> AutomationResult` for manual runs.
- Cron parsing via `croniter`; date-window gating via
  `parse_iso_date` (from `automation.models`).

## Steps / Flow

`_loop`, once started:

1. `_auto_disable_expired()` → disables enabled scheduled automations whose
   `end_date` has passed (persists via the state store).
2. `_enabled_scheduled()` → manager's scheduled automations filtered by
   `is_enabled`.
3. `_nearest_time(jobs)` → earliest `_wake_time` (or `None`). `_wake_time`
   returns the window start for a pending future automation so the loop wakes
   the day it activates, and the cron next-fire otherwise.
4. `_wait(delay)` sleeps until that time, or until `notify_changed()` / `stop()`
   fires (via two waiter tasks + `asyncio.wait(FIRST_COMPLETED)`).
5. If woken by a change, recompute. Else `_run_due()` runs every automation whose
   `_next_time` has passed (sequentially). `_next_time` returns `None` outside
   the date window, so out-of-window automations never fire.
6. `_execute` runs the automation, `manager.record_run(...)`, then invokes
   `on_result(result)`.

### Local time

`_next_time` uses `croniter(expr, datetime.now()).get_next(datetime).timestamp()`.
`get_next(float)` is avoided because it returns a timestamp that is off by the
local UTC offset.

## Function Reference

### Public

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, manager, runner, on_result: Callable[[AutomationResult], None]) -> None` | manager; runner; callback | `None` | init event flags | — |
| `def start(self) -> None` | — | `None` | `ensure_future(_loop)` if not running | Logs start |
| `async def stop(self) -> None` | — | `None` | set stop + wake, cancel + await task | Logs stop |
| `def notify_changed(self) -> None` | — | `None` | set wake event | — |
| `async def run_now(self, automation) -> AutomationResult` | automation | result | `_execute(automation)` | Fires `on_result`; records run |

### Private

| Signature | Purpose |
|---|---|
| `async def _loop(self) -> None` | wait/run loop; swallows cancellation |
| `async def _run_due(self) -> None` | run all due automations |
| `async def _execute(self, automation) -> AutomationResult` | run + record + callback |
| `def _enabled_scheduled(self) -> list[AutomationInfo]` | enabled scheduled set |
| `def _auto_disable_expired(self) -> None` | disable automations past `end_date` |
| `def _in_window(self, automation) -> bool` | whether the date window covers today |
| `def _next_time(self, automation) -> float \| None` | next cron fire (local); `None` out of window |
| `def _wake_time(self, automation) -> float \| None` | next wake; window start for pending automations |
| `def _nearest_time(self, automations) -> float \| None` | earliest next wake |
| `async def _wait(self, delay: float \| None) -> bool` | sleep/wake helper |

## See also

- [automation-manager](automation-manager.md) — schedules and state.
- [automation-runner](automation-runner.md) — execution.
- [notification-lifecycle-flow](../flows/notification-lifecycle-flow.md) — where results land.
- [qt-automation-controller](qt-automation-controller.md) — starts the scheduler.
