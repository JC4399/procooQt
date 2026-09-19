# Procoo Qt Rebuild Plan

> **Single source of truth** for the Flet → Qt Quick/QML reconstruction. This document is both the
> concept reference (purpose, deliverables, source mapping, acceptance tests) and the nested todo
> list. Update the checkboxes as work lands.

**Status legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

**Current phase:** `[x]` **P8 Polish & Parity** done (P0–P8 complete; optional M6 deferred).

---

## 1. Purpose & Goals

Rebuild the Procoo Agent Assistant's GUI from **Flet** to **Qt Quick / QML** while preserving the
backend, behavior, and terminal-style square/flat dark aesthetic. The port also introduces cleaner
code-level naming (controllers instead of mixins, `_handle_*` slots, explicit model classes) and
replaces hand-rolled markdown rendering with a real markdown engine.

Non-goals: rewriting the agent/skill/session backend; changing domain terminology (skill, preset,
session, tool, mode); adding features not in the Flet edition.

## 2. Locked Decisions

| Decision | Choice |
|---|---|
| Layout | Self-contained `procooQt/` project; backend copied verbatim |
| UI toolkit | Qt Quick / QML directly (no intermediate Qt Widgets port) |
| Qt binding | PySide6 (LGPL) |
| Async | `qasync` fuses asyncio with the Qt event loop (single loop, GUI thread) |
| Tool execution | `asyncio.create_subprocess_exec` (unchanged); **not** `QProcess` |
| Cross-thread | `watchdog` thread → Qt `Signal` (queued) only |
| Control style | Qt Quick Controls **Basic** + custom `Theme` singleton (square, flat, `radius: 0`) |
| Editor | QML `TextArea` + `QSyntaxHighlighter` attached to its `textDocument` |
| Chat markdown | `markdown-it-py` + `mdit-py-plugins` + `pygments` → HTML → `TextEdit.RichText` |
| Tool-call args | Custom YAML highlighter retained (`yaml_highlight.py`) |
| Storage | **Fresh** `procooQt/storage/`; skills **shared** at `../skills` |
| Naming | Code-level only (Controller composition, `_handle_*` slots) |
| Structure for first port | Mirror the Flet layout 1:1; idiomatic QML refactor deferred |

## 3. Architecture

```
                 qasync.QEventLoop  ⇄  Qt Quick render loop   (one process, one thread)
                        │
   Agent.run() task ────┤  asyncio.Queue[event]  ──►  ChatListModel (QAbstractListModel) ──► QML delegate
   asyncio.gather ──────┤  asyncio.create_subprocess_exec  (tool scripts)
   watchdog thread ─────┘  Qt Signal (queued)  ──►  SkillController slot  ──►  models
```

- **QML is view-only.** All logic lives in Python controllers/models exposed as context properties.
- **`session.messages` is canonical**; `ChatListModel` is a derived render plan rebuilt via the same
  content-hash divergence logic the Flet renderer used.
- **Composition**: `ProcooQtUI` owns `SessionController`, `ChatController`, `SkillController`,
  `EditorController`. No multiple inheritance.

### Backend reuse map

| Package | Reuse | Notes |
|---|---|---|
| `src/config/` | Verbatim | pure sync YAML |
| `src/session/` | Verbatim | async; runs on the qasync loop |
| `src/skill/` | Verbatim | watchdog callback marshalled via signal |
| `src/util/` | Verbatim | only "Flet"→"Qt" docstrings + logger name changed |

### Source map (Flet → Qt)

| Flet source | Qt target |
|---|---|
| `src/flet/ui.py` (463) | `src/qt/ui.py`, QML `Main.qml` |
| `src/flet/theme.py` (288) | `src/qt/theme.py` (exposed as the `Theme` context property) |
| `src/flet/session_state.py` (92) | `src/qt/session_state.py` |
| `src/flet/session_panel.py` (742) | `src/qt/session_controller.py` + `models/session_list_model.py` + `panels/SessionPanel.qml` |
| `src/flet/session_lifecycle.py` (466) | `src/qt/session_controller.py` (lifecycle section) |
| `src/flet/chat_panel.py` (1076) | `src/qt/chat_controller.py` + `models/chat_list_model.py` + `panels/ChatPanel.qml` |
| `src/flet/chat_loop.py` (571) | `src/qt/chat_controller.py` (streaming section) |
| `src/flet/chat_widgets.py` (707) | `src/qt/chat_items.py` + `qml/cards/*.qml` |
| `src/flet/context_banner.py` (95) | `src/qt/chat_items.py` + `qml/cards/ContextBanner.qml` |
| `src/flet/skill_panel.py` (1276) | `src/qt/skill_controller.py` + `models/skill_tree_model.py`, `models/tool_mode_model.py` + `panels/SkillPanel.qml` |
| `src/flet/editor_panel.py` (748) | `src/qt/editor_controller.py` + `models/file_tree_model.py` + `panels/EditorPanel.qml` + `src/qt/highlighter.py` |
| `src/flet/syntax_highlight.py` (433) | `src/qt/yaml_highlight.py` (YAML only) + `src/qt/markdown.py` (new) |
| `src/flet/error_handler.py` (141) | `src/qt/error_handler.py` + QML `Toast.qml` |

### Naming glossary

`*Mixin → *Controller` · `ProcooFletUI → ProcooQtUI` · `page → engine/root` ·
`_on_*_click/_on_* → _handle_*` · `SessionUIState → SessionState` · `*_col → *_panel` ·
`chat_list → ChatListModel` · `procoo_flet → procoo_qt`.

## 4. Concurrency Model

- `src/app.py`: `QApplication` → `QQuickStyle.setStyle("Basic")` → register font → create
  `qasync.QEventLoop(app)` → `asyncio.set_event_loop(loop)` → `ProcooQtUI` → load `Main.qml` →
  `loop.run_forever()`.
- Each generation = one `asyncio.ensure_future(agent.run(msg))`. The drain loop uses
  `await asyncio.wait_for(queue.get(), 0.1)` exactly as Flet did.
- Approval = `asyncio.Event` set from a `@Slot` when the user clicks Approve/Deny.
- Concurrent sessions = several tasks on the one loop; each writes its own `ChatListModel`.
- Watchdog: `SkillManager.start_watching(callback)` runs `callback` on a background thread →
  callback emits a signal → slot runs on GUI thread.
- Never block the loop: `await asyncio.to_thread(...)` for sync file I/O.

## 5. Data & Paths

```
procooQt/config/config.yaml   -> skills_dir "../skills" (shared), storage_dir "./storage" (fresh)
procooQt/storage/             -> sessions/<id>.json, folders.json
../skills/                    -> shared skill library + _presets/
```
`app.py` resolves relative `skills_dir` / `storage_dir` against `_PROJECT_ROOT` (= `procooQt/`).
`config/config.yaml` is gitignored; `config_template.yaml` is committed.

---

## 6. Work Breakdown

### P0 — Scaffold `[x]`

- **Purpose:** runnable skeleton: project layout, backend copy, qasync entry, QML shell, theme,
  conventions, this plan.
- **Deliverables:** `procooQt/pyproject.toml`, `AGENTS.md`, `wiki/00-Rebuild-Plan.md`,
  `qt-docs/README.md`, `src/app.py`, `src/qt/*` stubs, `qml/**`, `.gitignore`, batch scripts.
- **Source reference:** `src/app.py`, `src/flet/ui.py`, `src/flet/theme.py`; wiki `modules/app`,
  `modules/flet-theme`, `modules/flet-ui`.
- **Depends on:** nothing.
- **Test / DoD:** `uv sync` succeeds; `ruff check` and `ty check` clean; offscreen smoke test loads
  `Main.qml` and exits 0; 3-pane window renders with theme colours.
- **Sub-tasks:**
  - [x] Create directory tree
  - [x] Copy backend (`config`/`session`/`skill`/`util`) + font + `config.yaml`/template
  - [x] Write `pyproject.toml`, `.gitignore`, `qt-docs/README.md`
  - [x] Write `AGENTS.md` (Qt/QML conventions)
  - [x] Write `wiki/00-Rebuild-Plan.md`
  - [x] Scaffold `src/qt/` package + `src/app.py`
  - [x] Scaffold `qml/` shell (`Main.qml`, panel placeholders)
  - [x] Create venv, install deps, run ruff + ty + offscreen smoke test
  - [x] Add `[dependency-groups]` dev tooling (`ruff`, `ty`) + launch scripts
  - [x] Back-port `config/manager.py` ty/ruff fixes to the Flet edition
  - [x] _Review checkpoint_ ← **you are here**

### P1 — Qt/QML Foundations `[x]`

- **Purpose:** wire backend subsystems, qasync loop, QML engine, theme bridge, and the model
  infrastructure every panel builds on.
- **Deliverables:** `src/qt/ui.py` (full `ProcooQtUI` composition + context properties),
  `src/qt/theme.py` (`Theme` QObject exposed as a context property), `src/qt/models/base.py`
  (role `IntEnum`, `ListModel` base), engine property exposure, font registration, `qt_roles`.
- **Source reference:** `src/flet/ui.py:35-296` (`__init__`, build sequence, `_resize_panel`),
  `src/flet/theme.py`; wiki `modules/flet-ui`, `modules/flet-theme`, `modules/app`.
- **Depends on:** P0.
- **Test / DoD:** app starts from `config/config.yaml`, logs model/api_base; QML binds
  `Theme.colorPageBg`; `app` context property resolves; `SplitView` panes resize; `ty check` clean.
- **Sub-tasks:**
  - [x] `ProcooQtUI` construction/ownership of 4 controllers + `SessionState` registry
  - [x] Expose `app`, `theme`, `session`, `chat`, `skill`, `editor` to QML
  - [x] `Theme` QObject with all `theme.py` constants, exposed to QML
  - [x] `qt_roles.py`: role `IntEnum`s + helpers
  - [x] `models/base.py`: reusable `ListModel` base (roles, apply-diff helper)
  - [x] Register `Sarasa Fixed TC` via `QFontDatabase.addApplicationFont`
  - [x] `Main.qml` 3-pane `SplitView` + responsive `sizeChanged` defaults

### P2 — Session List & Lifecycle `[x]`

- **Purpose:** session sidebar + create/switch/delete/hydrate/persist, folders, status, auto-select,
  validation toasts.
- **Deliverables:** `SessionController`, `SessionListModel`, `SessionState`,
  `SessionTile.qml`, `FolderHeader.qml`, `NewFolderDialog.qml`; folder grouping; status blink.
- **Source reference:** `src/flet/session_panel.py`, `src/flet/session_lifecycle.py`,
  `src/flet/session_state.py`; wiki `modules/flet-session-panel`, `modules/flet-session-lifecycle`,
  `modules/flet-session-state`, `flows/session-lifecycle-flow`.
- **Depends on:** P1.
- **Test / DoD:** create/switch/delete round-trips to `procooQt/storage/sessions/*.json`; latest
  session auto-selected at startup; status dot reflects `SessionStatus`; `folders.json` updates.
- **Sub-tasks:**
  - [x] `SessionListModel` roles: id, title, status, folder, blinking, active
  - [x] Derive title/status (port `_derive_session_title`, `_derive_session_status`)
  - [x] `SessionTile.qml` + selection + status dot `SequentialAnimation`
  - [x] Folder grouping + expand/collapse
  - [x] `_handle_new_session`, `_handle_session_click`, `_handle_delete_session`
  - [x] `_hydrate_session` (skill contents + tool defs via `SkillManager`)
  - [x] `_save_current_session_for` + context snapshot
  - [x] `_auto_select_session` + `_emit_validation_issues` toasts
  - [x] P8 (drag-drop) hooks reserved — deferred to P8

### P3 — Chat Model & Streaming `[x]`

- **Purpose:** chat list, incremental render, input row, send/stop/regenerate, streaming event drain,
  compaction.
- **Deliverables:** `ChatController`, `ChatListModel`, `ChatPanel.qml`, `UserCard.qml`,
  `ThinkingCard.qml`, `ResponseCard.qml`, `ToolCallCard.qml`, `ToolResultCard.qml`, `TokenBar.qml`.
- **Source reference:** `src/flet/chat_panel.py`, `src/flet/chat_loop.py`; wiki
  `modules/flet-chat-panel`, `modules/flet-chat-loop`, `flows/agent-turn-flow`.
- **Depends on:** P1 (+P2 for active session).
- **Test / DoD:** send a message to the local LLM; thinking/response stream live with token counts;
  Stop cancels; Regenerate re-runs; pending cards swap to results; session persists on turn end.
- **Sub-tasks:**
  - [x] `ChatListModel` with item kinds + roles (kind, title, bodyHtml, tokenText, collapsed, isPending, mode, toolName)
  - [x] Port `_compute_render_keys` / `_find_divergence` / `_build_suffix_items` to model diffs
  - [x] `_handle_send` + input `TextArea` (Enter/Shift+Enter) + Send/Stop/Regenerate buttons
  - [x] `_run_chat_loop` (hydrate / consume-events / cleanup phases)
  - [x] Streaming update throttle (1s for content-only; immediate for structural)
  - [x] `_swap_pending_result_card` equivalent
  - [x] Loading spinner (`BusyIndicator`) on session switch
  - [x] `_compact_session` / summarization on limit exceeded
  - [x] Concurrent-session model isolation

### P4 — Markdown & YAML Cards `[x]`

- **Purpose:** real markdown rendering for thinking/response; YAML highlighting for tool arguments;
  context banners.
- **Deliverables:** `src/qt/markdown.py` (`render_markdown` → HTML; `pygments` fenced code),
  `src/qt/yaml_highlight.py` (span→HTML), `ContextBanner.qml`, card body wiring.
- **Source reference:** `src/flet/chat_widgets.py`, `src/flet/context_banner.py`,
  `src/flet/syntax_highlight.py`; wiki `modules/flet-chat-widgets`, `modules/flet-context-banner`,
  `modules/flet-syntax-highlight`.
- **Depends on:** P3.
- **Test / DoD:** markdown headers/lists/links/tables/fenced code render correctly and selectably;
  YAML tool args colourised; delta banners use the orange scheme; pending cards inherit header style.
- **Sub-tasks:**
  - [x] `markdown-it-py` + `mdit-py-plugins` + `pygments` renderer
  - [x] Port YAML tokenizer to HTML spans
  - [x] Card item builder base helper (header → token → body → collapse)
  - [x] All 5 card kinds + pending variants
  - [x] `ContextBanner.qml` + delta variant
  - [x] Collapsible animation

### P5 — Approval & Token Bar `[x]`

- **Purpose:** tool-approval workflow (allow/ask/block) and live token accounting.
- **Deliverables:** `ApprovalBar.qml` (approve/deny + deny reason), token bar bindings,
  `@Slot` handlers.
- **Source reference:** `src/flet/chat_loop.py` (`_handle_approval`, `_on_approve`, `_on_deny`,
  `_on_stop`), `src/flet/chat_panel.py` (`_build_token_bar`, `_update_token_bar`); wiki
  `flows/tool-approval-flow`, `modules/flet-chat-loop`.
- **Depends on:** P3.
- **Test / DoD:** `ask` tool pauses generation and shows the bar; Approve executes, Deny returns the
  denial message, Stop cancels; token bar shows true input/output counts from `token_usage`.
- **Sub-tasks:**
  - [x] `_handle_approval` blocking on `asyncio.Event`
  - [x] `ApprovalBar.qml` show/hide + deny reason
  - [x] `_handle_approve` / `_handle_deny` / `_handle_stop`
  - [x] Approval button reset (QML `resolving` gate + controller visibility)
  - [x] Token bar model properties + `_update_token_bar`

### P6 — Skill Panel & Config Sync `[x]`

- **Purpose:** skill tree (primary/secondary), per-tool modes, presets, search, active-config bar,
  live config sync + delta banner, file-watcher refresh.
- **Deliverables:** `SkillController`, `SkillTreeModel`, `ToolModeModel`, `SkillPanel.qml`,
  `SkillNode.qml`, `ToolGroup.qml`, `PresetBar.qml`, `ActiveConfigBar.qml`.
- **Source reference:** `src/flet/skill_panel.py`; wiki `modules/flet-skill-panel`,
  `flows/config-sync-flow`, `flows/skill-discovery-flow`, `modules/skill-manager`.
- **Depends on:** P2, P3.
- **Test / DoD:** toggling a skill/tool mode calls `update_session_config`, persists, appends a delta
  context banner; presets load/save/delete; editing a `SKILL.md` on disk refreshes the tree via the
  watcher signal.
- **Sub-tasks:**
  - [x] `SkillTreeModel` (folder nesting; checkbox states)
  - [x] `ToolModeModel` (allow/ask/block radios grouped by skill)
  - [x] `_collect_selected_skills` / `_collect_tool_modes` (DRY)
  - [x] `_sync_config_to_session` + delta section builder
  - [x] `_load_config_into_sidebar` / `_rebuild_skill_sidebar`
  - [x] Preset load/save/delete via `PresetStore`
  - [x] Search filter + clear
  - [x] `_update_active_config_bar` chips
  - [x] Watchdog callback → signal → refresh

### P7 — Editor & File Tree `[x]`

- **Purpose:** Editor tab with code editor + collapsible file tree rooted at the skills dir.
- **Deliverables:** `EditorController`, `FileTreeModel`, `EditorPanel.qml`, `FileNode.qml`,
  `src/qt/highlighter.py` (QSyntaxHighlighter + TextArea bridge), edit/save/reload/cancel.
- **Source reference:** `src/flet/editor_panel.py`; wiki `modules/flet-editor-panel`.
- **Depends on:** P1.
- **Test / DoD:** open a skill script, syntax colours render, edit → save writes disk, reload/cancel
  restore; extension→language/icon mapping preserved; editing is read-only until Edit is pressed.
- **Sub-tasks:**
  - [x] `FileTreeModel` (depth flattening, icons by extension)
  - [x] `_build_file_tree` / `_open_file_in_editor` / `_load_file_into_editor`
  - [x] `CodeHighlighter` for python/yaml/md/json (+ bridge to `TextArea.textDocument`)
  - [x] Edit/Save/Cancel/Reload `@Slot`s (`Path.read_text`/`write_text` via `to_thread`)
  - [x] `EditorPanel.qml` `SplitView` (editor | file tree)
  - [x] Language/icon maps ported

### P8 — Polish & Parity `[x]`

- **Purpose:** close remaining gaps: drag-drop, toasts, blink, concurrent switching, banners,
  performance, parity pass.
- **Deliverables:** `Toast.qml` + toast signal, `Drag`/`DropArea` folder drop, per-session model
  cache, parity checklist sign-off.
- **Source reference:** `src/flet/session_panel.py` (drag/drop), `src/flet/error_handler.py`,
  `src/flet/ui.py` (`_auto_select_session`, `_on_skill_files_changed`); wiki
  `modules/flet-error-handler`.
- **Depends on:** P2–P7.
- **Test / DoD:** all Section 9 parity items checked; no regressions vs the Flet app; `ruff` + `ty`
  clean; long sessions scroll smoothly.
- **Sub-tasks:**
  - [x] `ToastHost.qml` (bottom-right, 5s auto-dismiss) + `toast_requested` signal routing from all controllers
  - [x] `handle_error` routing (brief toast, detail to log)
  - [x] Session tile `Drag` + folder `DropArea` + unfiled drop zone
  - [x] Blink animation for running/waiting sessions
  - [x] Per-session `ChatListModel` cache for instant switching
  - [x] Render-key performance pass on large histories (`diff_update` suffix rebuild; `update_item` streaming)
  - [x] Full parity checklist walkthrough
  - [ ] Optional M6: idiomatic QML restructure — intentionally deferred (out of P8 scope)

---

## 7. Milestones

| Milestone | Parts | Exit criteria |
|---|---|---|
| **M0 Scaffold** | P0 | app skeleton runs, tooling green | 
| **M1 Shell** | P1 | theme + engine + models infra working |
| **M2 Sessions** | P2 | session CRUD persists |
| **M3 Chat** | P3, P4, P5 | streaming chat + approval + markdown |
| **M4 Skills** | P6 | config sync + presets + watcher |
| **M5 Editor** | P7 | edit/save skill scripts |
| **M6 Polish** | P8 | parity checklist signed off |

## 8. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Chat render engine rewrite (model diff) | Port the proven content-hash divergence logic; keep `session.messages` canonical |
| `QSyntaxHighlighter` on QML `TextArea.textDocument` | Spike early in P7; fallback is a `QQuickWidget`-embedded `QPlainTextEdit` |
| Qt rich-text HTML subset differs from `ft.TextSpan` | Validate card styling in P4 against the Flet app |
| `qasync` + Python 3.14 stability | Smoke-tested in P0; if unstable, fall back to background asyncio thread + signals |
| Backend fork drift | Keep `src/{config,session,skill,util}` in sync; back-port fixes |
| LLM emits unsafe HTML in markdown | `TextEdit.RichText` does not execute script; optionally sanitize in `markdown.py` |
| Secret leakage | `config/config.yaml` gitignored; commit only the template |

**Open questions**
- [ ] Do we need `Material`-style widgets anywhere (popups/scrollbars) or keep fully Basic?
- [ ] Should the editor show line numbers in v1 (custom gutter) or defer?
- [ ] Keep `server.host/port` in config though the desktop app no longer serves web?

## 9. Parity Checklist (vs Flet edition)

- [x] Three-pane layout with resizable panels (Chat/Schedule left, Skills/Editor right)
- [x] Session tiles: title from first user message, status dot, running blink, active highlight
- [x] Create / switch / delete sessions; folder create/delete; drag session into folder
- [x] Auto-select latest session on startup; create fresh session when none exist
- [x] Skill tree with primary/secondary checkboxes; per-tool allow/ask/block
- [x] Preset dropdown load/save/delete; active-config chips; search filter
- [x] Live config sync + orange delta context banner; skill-file watcher refresh
- [x] Streaming thinking/response/tool-call/tool-result cards with token counts
- [x] Selectable markdown rendering (was hand-rolled) for thinking/response
- [x] Tool approval bar (approve/deny reason); Stop; Regenerate
- [x] Token bar with true input/output counts
- [x] Automatic summarization on size/token limit
- [x] Editor: file tree, open file, edit/save/reload/cancel, syntax highlighting
- [x] Error/warning toasts (5s, bottom-right); validation issues on startup
- [x] Concurrent sessions generate simultaneously while user switches

## 10. Reference Map

- **Backend wiki:** `../wiki/modules/` — `session-agent`, `session-manager`, `session-store`,
  `skill-manager`, `skill-preset`, `config-manager`, `util-*`.
- **UI wiki:** `../wiki/modules/flet-*` and `../wiki/flows/*` (behavior spec for this port).
- **Original UI code:** `../src/flet/` (read-only reference).
- **Qt/QML docs:** `../procooQt/qt-docs/`.
- **Conventions:** `../procooQt/AGENTS.md`.
