# ProcooQt — Qt Wiki

Procoo is a **Qt Quick / QML multi-panel chat UI** for interactive LLM agent
work. A **session** is a unit of work that owns a split-window layout of **chat**
panels; each panel has its own tab bar, skill dock, and config/token bar. Users
pick "skills" (bundles of instructions + tool scripts), configure per-tool
permissions, and converse with an LLM agent that can execute those tools via
subprocess with an approval workflow. The front end is QML views driven by
Python controllers and list models on a single `qasync` event loop.

## What the app does

- **Skill discovery** — recursively scans a `skills/` directory for
  `SKILL.md` files and auto-infers tool schemas from Python scripts via AST.
- **Sessions & chats** — a *session* groups chats and remembers its split
  layout; each *chat* is a conversation persisted as JSON. The title bar holds a
  session selector; chats live in per-panel tab bars.
- **Split workspace** — up to four equal-width chat panels per session; drag a
  tab onto a panel half to split, onto another tab bar to regroup.
- **Tool approval workflow** — every tool call is tagged `allow` / `ask` /
  `block`; `ask` mode pauses generation until the user approves or denies.
- **Streaming chat** — thinking/reasoning, response text, and tool calls are
  rendered live as cards with token counts.
- **Automatic summarization** — when a chat exceeds a configured size or token
  limit, the agent summarizes the history and starts a new chat from it.
- **Presets & editor** — save/load skill+tool config presets, and a
  syntax-highlighted code editor with a file tree.

## Feature highlights

| Feature | Where |
|---|---|
| Split workspace + title-bar session selector (QML) | [`qt-ui`](modules/qt-ui.md) |
| Per-panel chat model (busy/approval/tokens/config counts) | [`qt-chat-panel-model`](modules/qt-chat-panel-model.md) |
| ReAct agent loop + subprocess tool execution | [`chat-agent`](modules/chat-agent.md) |
| Tool approval (allow/ask/block) | [`flows/tool-approval-flow`](flows/tool-approval-flow.md) |
| Live incremental chat model (`QAbstractListModel`) | [`qt-chat-controller`](modules/qt-chat-controller.md) |
| Automatic chat summarization on size/token limit | [`qt-chat-controller`](modules/qt-chat-controller.md) |
| Skill discovery + AST schema inference | [`skill-manager`](modules/skill-manager.md) |
| Preset store | [`skill-preset`](modules/skill-preset.md) |
| Code editor + `QSyntaxHighlighter` | [`qt-editor-controller`](modules/qt-editor-controller.md) |
| Selectable markdown rendering | [`qt-markdown`](modules/qt-markdown.md) |
| LaTeX math in responses (in-memory, no files) | [`qt-latex`](modules/qt-latex.md) |

## Getting started

```
src/app.py            # entry point (qasync loop + QML bootstrap)
config/config.yaml    # paths and LLM settings (no server section)
../skills/            # shared skill library (SKILL.md + scripts/)
storage/              # sessions.json + chats/<chat_id>.json
```

Run from `procooQt/`:

```
uv run python -m src.app
```

or double-click `start_procoo_qt.bat` (activates `.venv` and runs the same
module). `skills_dir` points at the shared `../skills` library; `storage_dir`
points at `procooQt/storage/`.

## Documentation map

### Overview

- [Architecture](01-Architecture.md) — subsystems, data flow, key concepts.
- [Configuration](02-Configuration.md) — `config.yaml` schema and loading.

### Cross-module flows

- [Agent turn flow](flows/agent-turn-flow.md)
- [Tool approval flow](flows/tool-approval-flow.md)
- [Chat lifecycle flow](flows/chat-lifecycle-flow.md)
- [Config sync flow](flows/config-sync-flow.md)
- [Skill discovery flow](flows/skill-discovery-flow.md)

### Module reference

| Package | Pages |
|---|---|
| `src/` | [app](modules/app.md) |
| `src/config/` | [manager](modules/config-manager.md) |
| `src/chat/` | [agent](modules/chat-agent.md) · [llm](modules/chat-llm.md) · [manager](modules/chat-manager.md) · [store](modules/chat-store.md) |
| `src/skill/` | [manager](modules/skill-manager.md) · [models](modules/skill-models.md) · [preset](modules/skill-preset.md) |
| `src/util/` | [error](modules/util-error.md) · [log](modules/util-log.md) · [tokens](modules/util-tokens.md) · [venv](modules/util-venv.md) |
| `src/qt/` | [ui](modules/qt-ui.md) · [theme](modules/qt-theme.md) · [chat-panel-model](modules/qt-chat-panel-model.md) · [chat-state](modules/qt-chat-state.md) · [session-controller](modules/qt-session-controller.md) · [chat-controller](modules/qt-chat-controller.md) · [chat-items](modules/qt-chat-items.md) · [context-banner](modules/qt-context-banner.md) · [skill-controller](modules/qt-skill-controller.md) · [editor-controller](modules/qt-editor-controller.md) · [markdown](modules/qt-markdown.md) · [latex](modules/qt-latex.md) · [yaml-highlight](modules/qt-yaml-highlight.md) · [highlighter](modules/qt-highlighter.md) · [error-handler](modules/qt-error-handler.md) · [models](modules/qt-models.md) · [qt-roles](modules/qt-qt-roles.md) |

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

Names follow the Qt toolkit: `QObject` controllers composed
by `ProcooQtUI`, `@Signal`/`@Slot` boundaries to QML, `_handle_*` handlers, the
`procoo_qt` logger, and QML views under `src/qml/`. Authoring conventions for the
Qt codebase live in [`../AGENTS.md`](../AGENTS.md).
