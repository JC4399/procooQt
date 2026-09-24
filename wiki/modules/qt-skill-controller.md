# qt.skill_controller — skill tree, tool modes, presets & config sync

Source: `src/qt/skill_controller.py`

## Purpose

Owns the skill dock's data: the flattened skill tree, per-tool permission
modes, saved presets, the search filter, and the config-sync flow that pushes
dock selections to the active chat and appends a delta context banner. It also
publishes per-chat config counts to the split panels and bridges the `watchdog`
skill-directory watcher onto the Qt GUI thread. QML stays view-only and calls
these slots.

## Deliverables

- `SkillTreeModel` (`skill.skill_model`) and `ToolModeModel` (`skill.tool_model`).
- `SkillController` (`QObject`) with signals, `Q_PROPERTY` accessors, and `@Slot`
  handlers for search, toggles, presets, and the watcher.
- `build` / `start` lifecycle.
- DRY collectors `_collect_selected_skills`, `_collect_tool_modes`,
  `_collect_sidebar_config`.
- Sync pipeline `_collect_*` → `_persist_config` → `_apply_live_config` →
  `_append_delta_banner` → `chat.rebuild_chat_display`.
- `_load_config_into_sidebar`, `_rebuild_skill_sidebar`, `_refresh_skills`.
- Per-chat summary publisher `_publish_config_summary` (primary/allow/ask/block
  counts on the chat's `ChatState`).
- Config-chip builders `_update_config_chips`, `_summary_chip`, `_chip` (legacy;
  no longer consumed by QML).

## Signals & properties

| Signal | Payload | Emitted when |
|---|---|---|
| `skills_changed` | — | Skill tree / search / selection changes; also notifies `skill_model` + `searchText`. |
| `tool_modes_changed` | — | Tool model rebuilt; notifies `tool_model`. |
| `presets_changed` | — | Preset list reloaded; notifies `presetNames`. |
| `config_changed` | — | Active-config chip list rebuilt (legacy) — notifies `configChips`. |
| `preset_name_changed` | — | `presetName` set; notifies that property. |
| `toast_requested` | `str, str` | A user-visible message + toast level (`TOAST_ERROR` / `TOAST_WARNING` / `TOAST_INFO`). Preset save/load/delete emit `TOAST_INFO`; missing presets emit `TOAST_WARNING`. |
| `skill_files_changed` | — | Watchdog callback (background thread) → queued to the GUI slot. Also wired to `editor._handle_skill_files_changed` by `qt-ui`. |

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `skill_model` | `QObject` | `skills_changed` | Flattened skill tree for `SkillDock.qml`. |
| `tool_model` | `QObject` | `tool_modes_changed` | Tool rows grouped by skill. |
| `presetNames` | `list` | `presets_changed` | Sorted saved preset names. |
| `configChips` | `list` | `config_changed` | Legacy `{"label","bg","fg"}` chips; no longer consumed by QML (the split bar shows per-chat counts). |
| `searchText` | `str` | `skills_changed` | Current skill search term. |
| `presetName` | `str` | `preset_name_changed` | Typed save-preset name (writable). |

## Steps / Flow

### Build (`build`)

1. Create `SkillTreeModel` and `ToolModeModel`; initialise `_tool_modes` from
   `skill_manager.default_tool_modes()`.
2. Connect `skill_files_changed` → `_handle_skill_files_changed`.
3. `_refresh_presets(emit=False)`, `_rebuild_skill_sidebar`, `_update_config_chips`.

### Start (`start`)

1. `skill_manager.start_watching(self._on_skill_files_changed)`.
2. If a chat is active, `_handle_chat_activated(chat_id)`.

### Watcher marshalling

1. `watchdog` calls `_on_skill_files_changed` on a **background thread**; it only
   emits `skill_files_changed` and never touches models.
2. The connected `_handle_skill_files_changed` slot runs queued on the GUI thread
   and schedules `_refresh_skills`. `ProcooQtUI` connects the same signal to
   `editor._handle_skill_files_changed`, which independently reconciles the editor
   window (see [`qt-editor-controller`](qt-editor-controller.md)).
3. `_refresh_skills` `await asyncio.to_thread(skill_manager.refresh)`, then
   `_rebuild_skill_sidebar`. Failures toast an error.

### Sync (`_sync_config_to_chat`)

1. `_collect_sidebar_config` → `{primary, secondary, tools}` (DRY collectors).
2. `_persist_config` loads the stored chat, saves the new `skills_config`, and
   returns the previous tool-mode map.
3. `_update_config_chips` (legacy chips) and `_publish_config_summary(chat_id,
   config)` — the latter writes primary/allow/ask/block counts to the chat's
   `ChatState` and refreshes its panel.
4. `_apply_live_config`:
   - `await asyncio.to_thread(_load_config_payloads)` loads skill contents and
     tool definitions off the event loop.
   - `chat_manager.update_chat_config(...)` on the live chat; each warning emits
     `toast_requested`.
   - `_append_delta_banner` builds/pops the trailing delta banner.
   - `chat.rebuild_chat_display(chat_id)`.

### QML dock interaction (`SkillDock.qml`)

One `SkillDock.qml` is instantiated per `ChatPanel`. It is a zero-width overlay
anchored to the panel's right edge, collapsed by default (a thin rail) and
expanding leftward over the panel body.

- **Expand / collapse** — clicking the collapsed rail sets `expanded = true`;
  clicking the expanded panel's left rail collapses it or resizes it by drag.
- **Outside press collapses** — while expanded, a transparent `MouseArea`
  (`outsideCatcher`) covers this panel's body to the left of the expanded panel,
  full height below the tab bar. Pressing there sets `expanded = false` and
  passes the press through (`mouse.accepted = false`), so the same click still
  reaches the chat list or input. The catcher is scoped to its own
  `ChatPanel`; pressing another split panel leaves this dock untouched.
- **Preset load on select** — choosing a name in the `PresetBar` dropdown emits
  `loadRequested` (→ `_handle_load_preset`) immediately; there is no Load button.

## Function Reference

### Setup and lifecycle

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `__init__(app: ProcooApp, parent: QObject \| None = None) -> None` | `app` — backend owner; `parent` | `None` | `super().__init__(parent)`; stores `app`; `_tasks = set()` | None |
| `build(self) -> None` | — | `None` | Create both models, init state, connect watcher, refresh presets/sidebar/chips | Emits `skills_changed`, `config_changed` |
| `start(self) -> None` | — | `None` | Start skill watcher; load the active chat's config | Starts a watchdog observer thread |

### Slots: chat, search, toggles

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_handle_chat_activated(chat_id: str) -> None` | `chat_id` (empty = none) | `None` | Empty → clear selection + modes under `_loading_chat_config`; else `_load_config_into_sidebar` | Emits `tool_modes_changed`, `config_changed` |
| `_handle_search_changed(text: str) -> None` | `text` | `None` | Strips text, `_skill_model.rebuild(tree, search)`, emit | Emits `skills_changed` |
| `_handle_clear_search() -> None` | — | `None` | Calls `_handle_search_changed("")` | Emits `skills_changed` |
| `_handle_skill_toggle(path: str, kind: str, checked: bool) -> None` | `path`; `kind` (`primary`/`secondary`); `checked` | `None` | `set_selection` → `_refresh_tool_model` → emit; schedule sync unless loading | Emits `skills_changed`, `tool_modes_changed`; schedules sync |
| `_handle_tool_mode_change(tool_name: str, mode: str) -> None` | `tool_name`; `mode` | `None` | No-op if unchanged; update `_tool_modes` + model; schedule sync unless loading | Emits `tool_modes_changed`; schedules sync |
| `_handle_folder_toggle(path: str, expanded: bool) -> None` | `path`; `expanded` | `None` | `_skill_model.set_folder_expanded`, emit | Emits `skills_changed` |

### Slots: presets

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_handle_save_preset() -> None` | — (name from `presetName`) | `None` | Validate name (else error toast); collect config; `preset_store.save_preset`; refresh | Emits `preset_name_changed`, `presets_changed`, `toast_requested` (info on success, error on empty name) |
| `_handle_load_preset(name: str) -> None` | `name` (empty clears) | `None` | Empty → clear; else load, apply selection/modes under the loading flag, refresh chips, schedule sync | Emits `tool_modes_changed`, `config_changed`, `toast_requested` (info on load/clear, warning if preset missing); schedules sync |
| `_handle_delete_preset(name: str) -> None` | `name` | `None` | `preset_store.delete_preset`; clear typed name if it matched; refresh | Emits `preset_name_changed`, `presets_changed`, `toast_requested` (info on success) |

### Collectors (DRY)

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_collect_selected_skills() -> dict[str, list[str]]` | — | `{primary, secondary}` path lists | `_skill_model.collect_selected_primary/_secondary` | None |
| `_collect_tool_modes() -> dict[str, str]` | — | copy of `_tool_modes` | `dict(self._tool_modes)` | None |
| `_collect_sidebar_config() -> dict[str, Any]` | — | `{primary, secondary, tools}` | Collects selections + `skill_manager.build_tool_config(...)` | None |

### Sync pipeline

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_schedule_sync() -> None` | — | `None` | `_spawn(self._sync_config_to_chat())` | Schedules a task |
| `_spawn(coro) -> None` | `coro` | `None` | `asyncio.ensure_future`; tracked in `_tasks`; done callbacks discard + log | Schedules on the running loop |
| `_log_task_failure(task) static -> None` | `task` | `None` | Ignore cancelled; log non-`None` exception | Logs error |
| `_sync_config_to_chat() async -> None` | — | `None` | Bails while loading or when `_sidebar_chat_id` is empty; collect → persist → chips + summary → live apply | Persists, emits `config_changed`, updates the panel |
| `_persist_config(chat_id, config) -> dict[str, str]` | `chat_id`; `config` | previous tool-mode map | Load stored chat, replace `skills_config`, save | Writes chat file; `{}` if missing |
| `_apply_live_config(chat_id, config, old_tool_config) async -> None` | ids/config | `None` | Bails if no live chat; load payloads off-loop; `update_chat_config`; warnings → toast; append banner; rebuild chat | Emits `toast_requested`; mutates chat state |
| `_load_config_payloads(config) -> tuple[list, list, list, dict]` | `config` | primary content, secondary content, tool defs, tool config | Blocking `SkillManager` loads (run under `to_thread`) | None |
| `_append_delta_banner(chat_id, config, old_tool_config, result, primary, secondary, tool_defs) -> None` | sync inputs + result | `None` | Pops a trailing delta; if changes exist, appends a new delta banner to `state.context_banners_data` | Mutates chat state |

### Sidebar and model state

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_load_config_into_sidebar(chat_id: str) -> None` | `chat_id` | `None` | Read stored chat's `skills_config`; apply selection + modes under the loading flag; refresh tool model + chips + summary | Emits `tool_modes_changed`, `config_changed` |
| `_rebuild_skill_sidebar() -> None` | — | `None` | `_skill_model.rebuild(tree, search)`; re-apply modes; refresh tool model; emit | Emits `skills_changed` |
| `_refresh_tool_model() -> None` | — | `None` | `_tool_model.rebuild(all_tools, selected_union, modes, display_names)`; emit | Emits `tool_modes_changed` |
| `_apply_tool_modes(modes: dict) -> None` | `modes` | `None` | Merge over defaults for every discovered tool (missing → `"ask"`) | Replaces `_tool_modes` |
| `_refresh_presets(*, emit=True) -> None` | `emit` | `None` | Reload `preset_store.list_presets()` | Emits `presets_changed` when `emit` |

### Active-config summary and watcher

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_publish_config_summary(chat_id, config) -> None` | chat id, `{primary, secondary, tools}` | `None` | Set primary/allow/ask/block counts on `ChatState` → `session.refresh_chat_panels(chat_id)` | Updates the chat's panel |
| `_update_config_chips() -> None` | — | `None` | Legacy: build "Primary/Secondary/Allow/Ask/Block" summary chips | Emits `config_changed` |
| `_summary_chip(label, count, bg, fg) static -> dict[str, str]` | label/count/colors | `{label, bg, fg}` | `_chip(f"{label}: {count}", bg, fg)` | None |
| `_chip(label, bg, fg) static -> dict[str, str]` | label/colors | `{label, bg, fg}` | Builds a chip dict | None |
| `_on_skill_files_changed() -> None` | — | `None` | Background-thread callback: **emit only** | Emits `skill_files_changed` |
| `_handle_skill_files_changed() -> None` | — | `None` | GUI-thread slot; schedule `_refresh_skills` | Logs; schedules task |
| `_refresh_skills() async -> None` | — | `None` | `await asyncio.to_thread(skill_manager.refresh)`, then rebuild sidebar; toast on failure | Emits `toast_requested` on error |

## Related

- [`qt-context-banner`](qt-context-banner.md) — delta section builder.
- [`qt-chat-items`](qt-chat-items.md) — chat item builders the rebuilt display consumes.
- [`qt-editor-controller`](qt-editor-controller.md) — the same watcher signal drives editor reconciliation.
