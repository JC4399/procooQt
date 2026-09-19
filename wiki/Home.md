# Procoo Agent Assistant — Qt Wiki

Procoo is a **Qt Quick / QML multi-column chat UI** for interactive LLM agent
sessions. It lets a user select "skills" (bundles of instructions + tool
scripts), configure per-tool permissions, and converse with an LLM agent that
can execute those tools via subprocess with an approval workflow. The backend
is a fork of the Flet edition; the Qt front end replaces Flet controls with QML
views driven by Python controllers and list models on a single `qasync` event
loop.

## What the app does

- **Skill discovery** — recursively scans a `skills/` directory for
  `SKILL.md` files and auto-infers tool schemas from Python scripts via AST.
- **Session management** — create, switch, delete, and persist chat sessions
  (JSON files on disk) with folder grouping and concurrent generation.
- **Tool approval workflow** — every tool call is tagged `allow` / `ask` /
  `block`; `ask` mode pauses generation until the user approves or denies.
- **Streaming chat** — thinking/reasoning, response text, and tool calls are
  rendered live as cards with token counts.
- **Automatic summarization** — when a session exceeds a configured size or
  token limit, the agent summarizes the history and starts a new session
  seeded with that summary.
- **Presets & editor** — save/load skill+tool config presets, and a
  syntax-highlighted code editor with a file tree.

## Feature highlights

| Feature | Where |
|---|---|
| Multi-column QML layout (sessions / chat / skills) | [`qt-ui`](modules/qt-ui.md) |
| ReAct agent loop + subprocess tool execution | [`session-agent`](modules/session-agent.md) |
| Tool approval (allow/ask/block) | [`flows/tool-approval-flow`](flows/tool-approval-flow.md) |
| Live incremental chat model (`QAbstractListModel`) | [`qt-chat-controller`](modules/qt-chat-controller.md) |
| Automatic session summarization on size/token limit | [`qt-chat-controller`](modules/qt-chat-controller.md) |
| Skill discovery + AST schema inference | [`skill-manager`](modules/skill-manager.md) |
| Preset store | [`skill-preset`](modules/skill-preset.md) |
| Code editor + `QSyntaxHighlighter` | [`qt-editor-controller`](modules/qt-editor-controller.md) |
| Selectable markdown rendering | [`qt-markdown`](modules/qt-markdown.md) |

## Getting started

```
src/app.py            # entry point (qasync loop + QML bootstrap)
config/config.yaml    # paths and LLM settings (no server section)
../skills/            # shared skill library (SKILL.md + scripts/)
storage/              # fresh, Qt-only session storage
```

Run from `procooQt/`:

```
uv run python -m src.app
```

or double-click `start_procoo_qt.bat` (activates `.venv` and runs the same
module). `skills_dir` points at the shared `../skills` library; `storage_dir`
is a fresh `procooQt/storage/` never shared with the Flet app.

## Documentation map

### Overview

- [Architecture](01-Architecture.md) — subsystems, data flow, key concepts.
- [Configuration](02-Configuration.md) — `config.yaml` schema and loading.
- [Rebuild plan](00-Rebuild-Plan.md) — Flet → Qt port tracker and parity checklist.

### Cross-module flows

- [Agent turn flow](flows/agent-turn-flow.md)
- [Tool approval flow](flows/tool-approval-flow.md)
- [Session lifecycle flow](flows/session-lifecycle-flow.md)
- [Config sync flow](flows/config-sync-flow.md)
- [Skill discovery flow](flows/skill-discovery-flow.md)

### Module reference

| Package | Pages |
|---|---|
| `src/` | [app](modules/app.md) |
| `src/config/` | [manager](modules/config-manager.md) |
| `src/session/` | [chat](modules/session-chat.md) · [agent](modules/session-agent.md) · [manager](modules/session-manager.md) · [store](modules/session-store.md) |
| `src/skill/` | [manager](modules/skill-manager.md) · [models](modules/skill-models.md) · [preset](modules/skill-preset.md) |
| `src/util/` | [error](modules/util-error.md) · [log](modules/util-log.md) · [tokens](modules/util-tokens.md) · [venv](modules/util-venv.md) |
| `src/qt/` | [ui](modules/qt-ui.md) · [theme](modules/qt-theme.md) · [session-state](modules/qt-session-state.md) · [session-controller](modules/qt-session-controller.md) · [chat-controller](modules/qt-chat-controller.md) · [chat-items](modules/qt-chat-items.md) · [context-banner](modules/qt-context-banner.md) · [skill-controller](modules/qt-skill-controller.md) · [editor-controller](modules/qt-editor-controller.md) · [markdown](modules/qt-markdown.md) · [yaml-highlight](modules/qt-yaml-highlight.md) · [highlighter](modules/qt-highlighter.md) · [error-handler](modules/qt-error-handler.md) · [models](modules/qt-models.md) · [qt-roles](modules/qt-qt-roles.md) |

## Conventions used in this wiki

Each module page follows a fixed order:

1. **Purpose** — what the module/class is for.
2. **Deliverables** — what it produces (return values, files, events, UI).
3. **Steps / Flow** — ordered runtime steps.
4. **Function Reference** — per-function input/output tables.

Function reference tables use these columns:

| Column | Meaning |
|---|---|
| Signature | exact `def` line |
| Inputs | parameter name, type, meaning |
| Output | return type + semantics |
| Flow | step-by-step (non-trivial methods only) |
| Raises / Side effects | exceptions, mutations, emitted events |

The Qt edition names things after its toolkit: `QObject` controllers composed
by `ProcooQtUI`, `@Signal`/`@Slot` boundaries to QML, `_handle_*` handlers, the
`procoo_qt` logger, and QML views under `qml/`. Authoring conventions for the
Qt codebase live in [`../AGENTS.md`](../AGENTS.md).
