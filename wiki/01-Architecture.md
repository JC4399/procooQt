# Architecture

## System overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  src/app.py — ProcooApp (wiring) + main()                                    │
│    config = ConfigManager   skill_manager = SkillManager                     │
│    chat_store = ChatStore   preset_store = PresetStore                       │
│    automation_manager = AutomationManager  notification_manager = ...        │
│    subagent_manager = SubAgentManager                                        │
│                                                                              │
│    QApplication → QQuickStyle "Basic" → register font →                      │
│    qasync.QEventLoop(app) → asyncio.set_event_loop(loop) →                   │
│    QQmlApplicationEngine.load(src/qml/Main.qml) → loop.run_forever()         │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ one asyncio loop fused with the Qt GUI thread
┌──────────────▼───────────────────────────────────────────────────────────────┐
│        qasync.QEventLoop  ⇄  Qt Quick render loop  (the GUI thread)          │
│    + one QThread per chat (src/qt/chat_worker.py): each owns an Agent, a      │
│      ChatRenderer, and a private asyncio loop; results arrive as Qt signals.  │
│                                                                              │
│  ProcooQtUI (QObject orchestrator — composition, no inheritance)             │
│    SessionController  → workspace panels + ChatState registry + session menu │
│    SessionBus         → cross-window session-list change broadcast            │
│    ChatController     → ChatListModel per chat, streaming, approval          │
│    SkillController    → SkillTreeModel, ToolModeModel, presets, watcher      │
│    EditorController   → FileTreeModel, CodeHighlighter                       │
│    AutomationController → AutomationListModel + scheduler + event server     │
│    SubAgentController → local sub-agent HTTP server (backend only)           │
│    NotificationController → notification model, badges, history              │
│    Theme (context property)      ErrorNotifier (toasts context property)     │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ QML context props: ui, backend, Theme, toasts,
               │                    session, chat, skill, editor
┌──────────────▼───────────────────────────────────────────────────────────────┐
│  QML view layer (view-only; src/qml/)                                        │
│    Main.qml — ApplicationWindow: TitleBar (content tabs) + content stack      │
│    components/ TitleBar · SessionSelector · ChatTabBar · SkillDock ·          │
│                ConfigTokenBar · ApprovalBar · PresetBar · ToastHost ·         │
│                CardBodyText · KnightRiderSpinner · …                          │
│    panels/     SplitWorkspace · ChatPanel · EditorPanel ·                     │
│                AutomationPanel · NotificationPanel                            │
│    cards/      User · Thinking · Response · ToolCall · ToolResult ·          │
│                ContextBanner · CardBase · AutomationCard · NotificationCard   │
│    windows/    EditorWindow · NotificationHistoryWindow                       │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ binds model roles / calls @Slot methods
┌──────────────▼───────────────────────────────────────────────────────────────┐
│  Agent event stream → worker render → ChatListModel → QML delegates          │
│    ChatWorker (QThread) owns Agent.run() ──asyncio.Queue[event]──► render    │
│      → chat_items builders (role dicts)                                       │
│      → Qt signal ──► ChatController apply slot → ChatListModel.diff_update    │
│      → ListView delegate switches on model.kind                              │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ uses
┌──────────────▼───────────────────────────────────────────────────────────────┐
│  src/chat/      ChatManager ──creates──► Agent (ReAct loop)                  │
│                 Agent ──► OpenAIModel (llm.py)                               │
│                 ChatStore (chats/*.json + chat_index.json + sessions.json)   │
│                 MediaStore (storage/media/<chat_id>/)                        │
├──────────────────────────────────────────────────────────────────────────────┤
│  src/skill/     SkillManager (discovery + AST schemas + watchdog)            │
│                 PresetStore (JSON presets) · models (Pydantic)               │
├──────────────────────────────────────────────────────────────────────────────┤
│  src/automation/ AutomationManager (discovery + state)                       │
│                 AutomationRunner/AutomationContext (headless agent bridge)   │
│                 AutomationScheduler (croniter) · AutomationEventServer       │
│                 (aiohttp)                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│  src/subagent/  SubAgentManager (spec validation + in-memory records)        │
│                 SubAgentServer (aiohttp) → chat_manager → Agent              │
├──────────────────────────────────────────────────────────────────────────────┤
│  src/notification/ NotificationManager/Store (storage/notifications.json)    │
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
| Chat runtime | ReAct agent loop, LLM client, persistence | `src/chat/` |
| Skills | Discovery, loading, AST schema inference, presets, watcher | `src/skill/` |
| Automations | `AUTOMATION.py` discovery, cron scheduling, HTTP event dispatch, headless-agent runs | `src/automation/` |
| Sub-agents | Optional skill tool → localhost HTTP → headless agents with per-run model/skills/tools | `src/subagent/` |
| Notifications | Run-result storage, unread counts, history | `src/notification/` |
| UI controllers | Composition orchestrator + controllers + models | `src/qt/` |
| QML view | View-only panels, components, cards | `src/qml/` |
| Utilities | Errors, logging, token counting, venv | `src/util/` |

## Key concepts

### `chat.messages` (single source of truth)
An OpenAI-compatible list `[{role, content, tool_calls, ...}]` held on each
`Agent`. `_`-prefixed metadata keys (`reasoning_content` on assistant,
`_mode` on tool_calls, `_streaming_tool_calls`) are stored alongside OpenAI
fields and are non-standard metadata ignored by the API. The UI renders from
this list; `ChatListModel` is a **derived** render plan, never a second source
of truth. `Agent._build_prompt` prepends the system prompt and forwards the
history. See [`chat-agent`](modules/chat-agent.md).

### Session vs chat
- A **session** is a unit of work. It owns a `sessions.json` record with a split
  layout (`splits: [{chat_ids, active_chat_id}]`, max 4) and groups its chats.
- A **chat** is a single conversation, stored as `storage/chats/<chat_id>.json`
  and carrying its own `session`, `skills_config`, `messages`, and
  `context_snapshot`.
- The title-bar **session selector** switches sessions; `SessionController`
  reconciles the stored layout against actual chat files and rebuilds the panels.
  A shared `SessionBus` broadcasts create/delete so every open window's title-bar
  list stays in sync.
- Each visible panel gets a `ChatPanelModel` (active chat, tab model, runtime
  values); `ChatController` renders to every visible chat.

### Event queue
Each `Agent` owns an `asyncio.Queue` (`event_queue`). During a turn it emits
events drained by its `ChatWorker._pump` on the worker thread, which renders them
and emits Qt signals to the GUI:

| Event type | Payload | Producer |
|---|---|---|
| `thinking` | `{text}` | reasoning step |
| `message` | `{text}` | reasoning step |
| `tool_call` | `{id, name, arguments, mode}` | tool resolution |
| `tool_call_streaming` | — | streamed tool args |
| `tool_result` | `{id, name, content, is_error}` | tool execution |
| `token_usage` | `{input, output, output_cumulative, input_previous}` | reasoning step |
| `media_user_message` | `{count}` | media injection |
| `done` | `{chat_id}` | end of turn |
| `error` | `{brief, detail, category}` | failures |

The worker maps these to `plan_ready` / `stream_updated` / `token_usage` /
`approval_needed` / `turn_finished` / `error` signals consumed by
[`ChatController`](modules/qt-chat-controller.md).

### Math rendering
Response bodies are Markdown rendered by [`qt-markdown`](modules/qt-markdown.md);
dollar-delimited LaTeX (`$…$`, `$$…$$`) is rasterised **in memory** by
[`qt-latex`](modules/qt-latex.md) and inlined as `data:` URI `<img>` tags. No
image files or cache directories exist: the LaTeX source lives in
`chat.messages`, and because `ChatListModel` is a derived render plan, the math
is re-rasterised whenever the plan is rebuilt. Math therefore survives restarts
without any persisted or pruned artefacts.

### Capabilities directory

The shared library lives under `capabilities/`, which holds two subsystems:

- `capabilities/skills/` — the skill library (see below).
- `capabilities/automations/` — automation scripts (see below).

`ConfigManager.capabilities_dir` is the root; `skills_dir` and `automations_dir`
are derived from it (or overridden explicitly). The
[editor controller](modules/qt-editor-controller.md) file tree is rooted at the
capabilities directory so it can open skill scripts and automation files.

### Skill paths

Skills are identified by their relative path from `skills_dir` (e.g.
`"coding/python"`). An **activated** skill's full instructions + tools are
loaded into the system prompt. See [`skill-manager`](modules/skill-manager.md).

### Automations

An automation is a directory containing `AUTOMATION.py` (YAML frontmatter +
`async def run(ctx)`) under `capabilities/automations/`. It runs either on a cron
`schedule` or on an `event` posted to the local HTTP server. `run(ctx)` receives
an `AutomationContext` whose `ask()` drives a temporary headless `Agent` (the
same ReAct loop as chat), so automations can use the LLM. Results are
`success` / `info` / `error`. See
[`automation-manager`](modules/automation-manager.md) and
[`automation-run-flow`](flows/automation-run-flow.md).

### Notifications

Every automation result becomes a notification: success → grey **log**, info →
amber **info**, error → red **error**. Logs are marked read when the notification
page opens and stay visible (dimmed) until it closes; info/error require
**Confirm** (errors also offer **Debug** which opens the source file). History
and read flags persist in `storage/notifications.json`. See
[`notification`](modules/notification.md) and
[`notification-lifecycle-flow`](flows/notification-lifecycle-flow.md).

### Sub-agents

The optional `capabilities/skills/basic/subagent/` skill exposes a `subagent`
tool. The tool script is a subprocess, so it calls a localhost HTTP server
(`SubAgentServer`, port `12842` by default) rather than touching `chat_manager`
directly. `SubAgentManager` validates the request, builds a temporary `Agent`
with an explicit model/skill/tool set, runs one prompt headless, and writes a
chat-style JSON transcript to the skill's `references/logs/` directory. The tool
receives only the final answer (or error) and the transcript path. Runs are
capped by a concurrency semaphore, bounded by a timeout, and nested sub-agents
are blocked. See [`subagent`](modules/subagent.md) and
[`subagent-flow`](flows/subagent-flow.md).

### Tool modes
Each tool maps to a permission mode:

| Mode | Behavior |
|---|---|
| `allow` | execute immediately |
| `ask` | pause for user approval |
| `block` | auto-deny with a message |

See [`flows/tool-approval-flow`](flows/tool-approval-flow.md).

### Concurrent chats
`ChatManager` holds multiple live `Agent`s keyed by chat ID. Each live chat runs
on its own [`ChatWorker`](modules/chat-worker.md) thread, which owns the `Agent`
and the render pipeline, so one chat's streaming and rendering never blocks
another. `SessionController` keeps a GUI-only `ChatState` per chat (busy/error,
approval info, true token counts, config counts) and `ChatController` keeps a
`ChatListModel` per chat, applying the worker's ready row updates on the GUI
thread. Threads free the GUI loop and parallelize network/tool I/O; pure-Python
Markdown rendering is still GIL-limited, and LaTeX/matplotlib is serialized.

## Data flow (one user message)

```
user submits (Enter / Send button; Enter lock hides in input row) → ChatPanel.submit
  → chat._handle_send_for(chat_id, text)     [optimistic user + waiting rows]
  → _launch_generation → _start_turn
     → session._hydrate_chat (build/restore Agent)
     → ChatController.attach_worker → ChatWorker.start_turn(message, gen)
        → Agent.run(message) shown on the worker thread   [Agent emits events]
           → _run_react_loop
              → _reasoning  → OpenAIModel stream
              → _resolve_tool_calls → run_tool (subprocess) / approval signal
        → _pump → _handle_event → plan_ready / stream_updated (Qt signal)
  → ChatController apply slots → ChatListModel.diff_update / update_item
  → _finalize (worker): final plan + chat JSON persist + compaction check
```

Full detail in [`flows/agent-turn-flow`](flows/agent-turn-flow.md).
