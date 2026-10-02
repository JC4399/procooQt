# Automation run flow

How an automation goes from discovery to an executed result, for all three
trigger paths.

Related: [automation-manager](../modules/automation-manager.md), [automation-runner](../modules/automation-runner.md), [automation-scheduler](../modules/automation-scheduler.md), [automation-server](../modules/automation-server.md), [qt-automation-controller](../modules/qt-automation-controller.md), [notification-lifecycle-flow](notification-lifecycle-flow.md).

## Library layout

```
capabilities/automations/
  <group>/
    <automation>/
      AUTOMATION.py     # frontmatter + async def run(ctx)
      scripts/          # optional
      references/       # optional
```

Discovery: `AutomationManager.rglob("AUTOMATION.py")`; the parent directory is the
automation, identified by its path relative to `automations_dir`. Enable/disable
and last-run live in `storage/automations.json`, not in the file.

## Triggers

| Trigger | Entry |
|---|---|
| Schedule | `AutomationScheduler._loop` → `_run_due` |
| External event | `AutomationEventServer._handle_event` |
| Manual (Run now) | `AutomationPanel.qml` card "Run now" button → `AutomationController._handle_run_now` |

All three call `AutomationRunner.run(automation, payload)`. Only the schedule
path honours the optional `start_date` / `end_date` frontmatter window:
`_next_time` skips firing outside the window, and the loop auto-disables an
enabled automation once `end_date` has passed (event and manual runs ignore the
window). Scheduled runs fire at the cron time planned before the loop's wait;
a run missed while the app is closed is skipped (no catch-up).

For the manual path the controller marks the automation's path in `_running` for
the duration, so the card shows a `KnightRiderSpinner` and disables the button
until the run completes (see
[qt-automation-controller](../modules/qt-automation-controller.md)).

## Sequence

### 1. Load (`AutomationRunner._compile_run_function`)

1. Read `AUTOMATION.py` (`asyncio.to_thread`); `frontmatter.loads(source).content`
   strips the YAML header.
2. `compile` + `exec` the body into a fresh namespace (`__file__` set).
3. Fetch `run`; it must be an `async def`, else the run resolves to an `error`.

### 2. Execute (`AutomationRunner.run`)

1. Build `AutomationContext(automation, config, skill_manager, skills_dir, payload)`.
2. Redirect stdout/stderr into a buffer; `await asyncio.wait_for(run(ctx), 1800)`.
3. The script returns a result dict; `_normalize` maps it to
   `success` / `info` / `error`.

### 3. LLM access (`AutomationContext.ask`)

Creates a temporary headless chat via `chat_manager` (the automation's skills,
all tools forced to `allow`), drains its event queue, returns the final assistant
text, then removes the chat. Agent errors raise `AutomationError`, which the
runner converts to an `error` result.

### 4. Publish

1. `manager.record_run(path, timestamp)`.
2. The caller invokes its `on_result` callback — the
   [automation controller](../modules/qt-automation-controller.md) emits
   `result_ready`, which the
   [notification controller](../modules/qt-notification-controller.md) turns into
   a notification (see [notification-lifecycle-flow](notification-lifecycle-flow.md)).

## Result contract

| `run()` returns | Kind | Notification |
|---|---|---|
| `{"status": "success", "message", "data"?}` | `success` | grey log |
| `{"status": "info", "message", "data"?}` | `info` | amber info |
| `{"status": "error", "message"}` | `error` | red error |
| `None` / `str` | `success` | grey log |
| bad shape / unknown status / exception | `error` | red error |

## Sample automations

- `capabilities/automations/hello_schedule/AUTOMATION.py` — cron `0 8 * * *`,
  calls `ctx.ask("hello world")` → `success`.
- `capabilities/automations/hello_event/AUTOMATION.py` — event `hello world`,
  returns `info` `"hello world"`.
