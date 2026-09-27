# Creating an Automation

## Purpose

An automation lets the user run work without opening a chat and without being
present. It is a Python program the app runs on a schedule or when an external
system reports an event; it may call the LLM through the same agent loop the chat
UI uses. An automation is the right form when the work is a task to be performed
on its own — a report built every morning, a notification sent when a system
flags something — rather than a conversation the user drives.

The agent is competent but knows nothing about the task until the automation
briefs it. A well-built automation states its purpose, its deliverable, and its
method the same way a skill does, so a future reader understands it without the
author present.

## Deliverable

A finished automation is a folder under `capabilities/automations/`:

```
automation-name/
├── AUTOMATION.py   # frontmatter + async def run(ctx)
├── scripts/        # optional tools (fixed input-to-output machines)
└── references/     # optional detail, rules, and guides
```

`AUTOMATION.py` is the required entry point: YAML frontmatter, then Python code
documented with skill-like comments (purpose, deliverable, methodology). It must
define `async def run(ctx)`, which returns one of:

| Return | Meaning | Shown to the user as |
|---|---|---|
| `{"status": "success", "message": str, "data": any?}` | The task completed | A grey success **log** (auto-read) |
| `{"status": "info", "message": str, "data": any?}` | A result meant for the user | An amber **info** card (Confirm) |
| `{"status": "error", "message": str}` | A step failed | A red **error** card (Confirm / Debug) |
| `None` or a `str` | Treated as success (`message` = the string) | A grey success **log** |

Anything else — an exception, a bad shape, an unknown status — becomes an
`error`. The app also captures stdout and stderr as the run log.

## Methodology

Author the parts in order, then test each activation path.

1. Align. Confirm what the automation does, how it is activated (a schedule or an
   event), and what it returns. Ask for the event name and payload shape, or the
   run time and frequency; ask what "done" means and which failures matter.
2. Write the briefing (`AUTOMATION.py` frontmatter and comment header): name,
   description, activation, and the purpose / deliverable / methodology.
3. Write the body: the `async def run(ctx)` function that does the work and
   returns a result dict.
4. Add `scripts/` or `references/` only if the work needs them (see
   `creating-script.md` for tools).
5. Test the happy path, the failure path, and the activation itself.

## Structure

### The folder location

Automations live beside skills under the shared capability library:

```
capabilities/
├── skills/         # SKILL.md folders
└── automations/    # AUTOMATION.py folders
    └── <group>/
        └── <automation>/
```

A directory is an automation if it (at any depth) contains an `AUTOMATION.py`.
The parent folders are grouping only. The automation's identity is its path
relative to `capabilities/automations/` (e.g. `reports/daily`).

### AUTOMATION.py — the frontmatter

The file starts with YAML frontmatter:

- **name** — the display name.
- **description** — what the automation does and when it matters. This is the
  label the user sees on the automation card.
- **activation** — `scheduled` or `event`. Required.
- **schedule** — a 5-field cron expression (e.g. `0 8 * * *` = every day at
  08:00). Required for `scheduled`. The expression is validated with `croniter`.
- **event** — the event name matched by the HTTP server. Required for `event`.
- **primary_skills** — optional list of skill paths to load into the
  automation's agent (their tools run without approval).
- **secondary_skills** — optional list of description-only skills.

The `description` value is a YAML plain scalar: never put `": "` (colon + space)
inside it, or the frontmatter fails to parse. Use a dash, or quote the value.

### AUTOMATION.py — the body

After the frontmatter, write the code with a comment header that states, in this
order: **Purpose** (why the automation exists), **Deliverable** (what a run
produces), and **Methodology** (the ordered steps). The code must define:

```python
async def run(ctx):
    ...
```

`run` must be `async`. It executes in-process on the application's single event
loop, so it must never block it: do CPU or file work in short steps, and use
`await` for anything that waits.

### The context (`ctx`)

`run(ctx)` receives an `AutomationContext`:

- `await ctx.ask(prompt) -> str` — run one headless agent turn (the same ReAct
  loop as chat) and return the assistant's reply. It uses the automation's
  `primary_skills`/`secondary_skills`, and every tool is forced to `allow`
  because no user is present to approve. Raises on agent failure.
- `ctx.payload` — a `dict` holding the JSON body the caller posted to the event
  server (empty `{}` for scheduled runs).
- `ctx.log(message)` — append a line to the run log. stdout/stderr are captured
  too.

### Activation

- **Scheduled.** While the automation is enabled, the app fires it at each cron
  time. Compute the expression against local time.
- **Event.** An external program posts to the event server:

  ```
  POST http://<host>:<port>/event/<event-name>
  Authorization: Bearer <key>     (or X-Api-Key: <key>, when auth is configured)
  Content-Type: application/json

  { ... optional payload ... }
  ```

  Every enabled automation whose `event` matches runs, and the HTTP response
  carries the results.

The user can enable/disable an automation and edit its folder from the
Automation page. Enable state and the last-run time are kept by the app
(`storage/automations.json`), not in `AUTOMATION.py`, so the file stays the
source of the work and the state stays out of it.

### scripts/ and references/

The same split as a skill: `scripts/` holds deterministic, reusable tools
(`creating-script.md`), and `references/` holds detail, rules, and guides opened
only when needed. Most automations need neither.

## Testing

Test each path before shipping:

- **Happy path** — run the automation (event: post the event; schedule: use the
  page's Run now) and confirm the returned status and message.
- **Failure path** — force a step to fail and confirm it returns an `error`
  result with a useful message.
- **Payload** — for event automations, confirm `ctx.payload` carries the posted
  JSON and that a missing or malformed body is handled.
- **LLM call** — when `ctx.ask` is used, confirm the agent returns text and that
  a tool the automation relies on is available.

## Checks

Before shipping the automation, confirm:

- The frontmatter name, description, and activation are present, and the
  schedule/event matches the activation.
- A scheduled expression is valid cron; an event name is non-empty.
- `run` is declared `async def run(ctx)` and returns a `success` / `info` /
  `error` dict.
- The comment header states purpose, deliverable, and methodology.
- The automation loads through the app's `AutomationManager`
  (`src/automation/manager.py`) with no validation errors — this is what catches
  malformed frontmatter.
- The work never blocks the event loop.
