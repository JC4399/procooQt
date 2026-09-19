# Architecture

## System overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  src/app.py — ProcooApp (wiring) + main()                                    │
│    config = ConfigManager   skill_manager = SkillManager                     │
│    session_store = SessionStore   preset_store = PresetStore                 │
│                                                                              │
│    QApplication → QQuickStyle "Basic" → register font →                      │
│    qasync.QEventLoop(app) → asyncio.set_event_loop(loop) →                   │
│    QQmlApplicationEngine.load(src/qml/Main.qml) → loop.run_forever()         │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ one asyncio loop fused with the Qt GUI thread
┌──────────────▼───────────────────────────────────────────────────────────────┐
│        qasync.QEventLoop  ⇄  Qt Quick render loop  (one process/thread)      │
│                                                                              │
│  ProcooQtUI (QObject orchestrator — composition, no inheritance)             │
│    SessionController  → SessionListModel, SessionState registry              │
│    ChatController     → ChatListModel per session, streaming, approval       │
│    SkillController    → SkillTreeModel, ToolModeModel, presets, watcher      │
│    EditorController   → FileTreeModel, CodeHighlighter                       │
│    Theme (context property)      ErrorNotifier (toasts context property)     │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ QML context props: ui, backend, Theme, toasts,
               │                    session, chat, skill, editor
┌──────────────▼───────────────────────────────────────────────────────────────┐
│  QML view layer (view-only; src/qml/)                                        │
│    Main.qml — ApplicationWindow + 3-pane SplitView                           │
│    src/qml/panels/     SessionPanel · ChatPanel · SkillPanel · EditorPanel   │
│    src/qml/cards/      User · Thinking · Response · ToolCall · ToolResult ·  │
│                        ContextBanner · CardBase                              │
│    src/qml/components/ SessionTile · FolderHeader · SkillNode · ToolGroup ·  │
│                        PresetBar · ActiveConfigBar · ApprovalBar · TokenBar ·│
│                        FileNode · ToastHost                                  │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ binds model roles / calls @Slot methods
┌──────────────▼───────────────────────────────────────────────────────────────┐
│  Agent event stream → ChatListModel → QML delegates                          │
│    Agent.run() ──asyncio.Queue[event]──► ChatController._consume_events      │
│      → chat_items builders (role dicts) → ChatListModel.diff_update          │
│      → ListView delegate switches on model.kind                              │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ uses
┌──────────────▼───────────────────────────────────────────────────────────────┐
│  src/session/   SessionManager ──creates──► Agent (ReAct loop)               │
│                 Agent ──► OpenAIChatModel (chat.py)                          │
│                 SessionStore (JSON persistence)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  src/skill/     SkillManager (discovery + AST schemas + watchdog)            │
│                 PresetStore (JSON presets) · models (Pydantic)               │
├──────────────────────────────────────────────────────────────────────────────┤
│  src/config/    ConfigManager (YAML, LLM validation)                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  src/util/      error/types · log/formatter · tokens/counter+tracker         │
│                 venv (tool subprocess interpreter resolution)                │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Subsystems

| Subsystem | Responsibility | Key files |
|---|---|---|
| Entry point / async | Boot config, fuse asyncio with Qt, load QML | `src/app.py` |
| Config | Load `config.yaml`, validate LLM | `src/config/manager.py` |
| Session runtime | ReAct agent loop, LLM client, persistence | `src/session/` |
| Skills | Discovery, loading, AST schema inference, presets, watcher | `src/skill/` |
| UI controllers | Composition orchestrator + 4 controllers + models | `src/qt/` |
| QML view | View-only panels, cards, components | `src/qml/` |
| Utilities | Errors, logging, token counting, venv | `src/util/` |

## Key concepts

### `session.messages` (single source of truth)
An OpenAI-compatible list `[{role, content, tool_calls, ...}]` held on each
`Agent`. `_`-prefixed metadata keys (`reasoning_content` on assistant,
`_mode` on tool_calls, `_streaming_tool_calls`) are stored alongside OpenAI
fields and are non-standard metadata ignored by the API. The UI renders from
this list; `ChatListModel` is a **derived** render plan, never a second source
of truth. `Agent._build_prompt` prepends the system prompt and forwards the
history. See [`session-agent`](modules/session-agent.md).

### Event queue
Each `Agent` owns an `asyncio.Queue` (`event_queue`). During a turn it emits
events consumed by `ChatController._consume_events`:

| Event type | Payload | Producer |
|---|---|---|
| `thinking` | `{text}` | reasoning step |
| `message` | `{text}` | reasoning step |
| `tool_call` | `{id, name, arguments, mode}` | tool resolution |
| `tool_call_streaming` | — | streamed tool args |
| `tool_result` | `{id, name, content, is_error}` | tool execution |
| `token_usage` | `{input, output, output_cumulative, input_previous}` | reasoning step |
| `media_user_message` | `{count}` | media injection |
| `done` | `{session_id}` | end of turn |
| `error` | `{brief, detail, category}` | failures |

### Skill paths
Skills are identified by their relative path from `skills_dir` (e.g.
`"coding/python"`). A **primary** skill's full instructions + tools are
loaded into the system prompt; a **secondary** skill contributes only a
description for on-demand discovery. See [`skill-manager`](modules/skill-manager.md).

### Tool modes
Each tool maps to a permission mode:

| Mode | Behavior |
|---|---|
| `allow` | execute immediately |
| `ask` | pause for user approval |
| `block` | auto-deny with a message |

See [`flows/tool-approval-flow`](flows/tool-approval-flow.md).

### Concurrent sessions
`SessionManager` holds multiple live `Agent`s keyed by session ID. `SessionController`
keeps a `SessionState` per session (generation task, approval event, streaming
card state, render keys) and `ChatController` keeps a `ChatListModel` per
session, so multiple sessions can generate simultaneously while the user
switches between them.

## Data flow (one user message)

```
user types / Enter → ChatPanel.submit → chat._handle_send(text)
  → _append_user_message → _launch_generation → _run_chat_loop
     → _hydrate_phase (build/restore Agent via session._hydrate_session)
     → session.run(message)          [Agent emits events]
        → _run_react_loop
           → _reasoning  → OpenAIChatModel stream
           → _resolve_tool_calls → run_tool (subprocess) / approval
     → _consume_events → _render_active_event
        → _rebuild_chat_display / _update_live_assistant (ChatListModel)
     → _finalize_turn → session._save_current_session_for (persist)
```

Full detail in [`flows/agent-turn-flow`](flows/agent-turn-flow.md).
