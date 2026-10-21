# Chat lifecycle flow

How sessions and chats are created, switched, laid out, hydrated, persisted, and
deleted.

Related: [`qt-session-controller`](../modules/qt-session-controller.md), [`qt-chat-state`](../modules/qt-chat-state.md), [`chat-manager`](../modules/chat-manager.md), [`chat-store`](../modules/chat-store.md).

## Entities

- A **session** is a named unit of work stored in `sessions.json` with a split
  layout (`splits: [{chat_ids, active_chat_id}]`, max 4). `Default` is created on
  first run.
- A **chat** is one conversation stored as `chats/<chat_id>.json` and carrying
  its own `session`, `skills_config`, `messages`, `model_name`, and
  `context_snapshot`.

```
(store)  --hydrate-->  (chat_manager / Agent)  <--ChatWorker persistence-->
   │                        ▲                                    │
   │                        └───────── _do_persist ────────────────┘
   ▼
(delete)  --remove-->  gone from store + manager + panels
```

`SessionController` owns `_panels` (the workspace layout), the `ChatState`
registry, the active session name, and the active chat id. `ChatController` is
notified through `active_chat_changed` and `chat_switch_started`, and renders to
every visible chat (`set_visible_chats`). Each panel's values reach QML through a
`ChatPanelModel`.

## Start / switch session (`SessionController.start`, `_handle_switch_session`)

1. `_emit_validation_issues()` surfaces skill ERROR/WARNING toasts.
2. `ensure_default_session()` creates `Default` when no session exists.
3. `_refresh_model()` → `_collect_summaries` (one disk parse per chat) →
   `_apply_summaries` (seed per-chat counts and persisted true token counts,
   group chats by session, update the session menu, `_sync_panels`).
4. `_reconcile_panels(name)` reads the stored layout, keeps only chats that still
   exist, appends chats missing from the layout to the first panel, drops empty
   panels (min 1), and saves.
5. `_sync_panels()` pushes each panel's active chat, `ChatListModel`, tabs, and
   runtime into its `ChatPanelModel`, then calls `chat.set_visible_chats(...)`.
   The setters are compare-and-emit and the tab model merges incrementally, so
   panels whose chat did not change are not disturbed.
6. `_open_session_panels()` opens each panel's active chat (`_open_chat`:
   `chat_switch_started` → off-thread load/hydrate → `active_chat_changed`).

## Create chat (`ChatTabBar` `+` → `session._handle_new_chat(slot)`)

1. `_generate_unique_chat_id` — timestamp id, suffixed on collision.
2. `_create_stored_chat` → `ChatStore.save_chat` with `session` = the active
   session, empty `messages`, and `true_input_tokens` / `true_output_cum` = `0`.
   The new record **inherits the panel's current chat's** `skills_config` and
   `model_name`, so a fresh chat continues the last working skill/tool setup and
   model; when no source chat exists these fall back to an empty config and the
   config default model.
3. Append the id to that panel's tabs and set it active; refresh + save layout;
   `_open_chat`.
4. The skill dock loads the inherited selections through `active_chat_changed` →
   `_load_config_into_sidebar`; later edits persist via the
   [config sync flow](config-sync-flow.md).

## Activate a tab (`ChatTabBar` click → `session._handle_panel_activate`)

Sets the panel's active chat, saves the layout, `_sync_panels`, and `_open_chat`.
`_open_chat` emits `chat_switch_started` (loading overlay), hydrates off-thread
if the chat isn't live, then emits `active_chat_changed`, which
`ChatController._handle_chat_activated` answers by attaching the chat's worker
and requesting a rebuild; the resulting plan is applied in batches behind the
opaque loading overlay (200 ms minimum).

Startup (`_open_session_panels`) opens **every** panel's active chat in one
synchronous burst, and closing the active chat auto-opens another, so several
`_rebuild_after_switch` coroutines can overlap. Staged builds are therefore
tracked **per chat** (`ChatController._staged_builds`), and each switch clears the
loading flag only when its own build completed (`_finish_switch_loading`); a
superseded build never hides the overlay over a partial transcript. On the QML
side the loading overlay re-arms auto-scroll and re-pins to the newest card when
it hides, so the freshly built transcript always scrolls to the bottom.

## Split / move (`SplitWorkspace` drag)

Panels live in a fixed set of **slots** (`SessionController.MAX_PANELS = 4`).
`SplitWorkspace.qml` drives a constant-size `Repeater` (`session.maxPanels`) and
positions each delegate from `session.panelOrder`, so adding, removing, or
moving a panel only changes a delegate's `x`/`visibility`. A panel therefore
keeps its `ChatPanelModel` as it moves and untouched panels are **never**
rebuilt.

- **Split** (`_handle_split(chat_id, target_slot, side)`): the target panel is
  kept (even if the dragged chat was its only tab) and a new panel is inserted
  left/right containing the chat, taking the lowest free slot. Max `MAX_PANELS`;
  the QML drop hint is suppressed at the limit.
- **Move** (`_handle_move_chat(chat_id, target_slot)`): the chat is removed from
  its panel and appended to the target's tabs; empty source panels collapse.
- Both snapshot the slot→active map first, then call `_rebuild_changed_panels`:
  only slots whose active chat actually changed have their model blanked
  (`chat.rebuild_chat_display`) and re-rendered by the chat's worker in staged
  batches behind the overlay, while the layout (and each panel's `x`) updates
  immediately. They then queue the layout persist and `_open_chat`, which
  activates the moved chat.

`SplitWorkspace.qml` tracks the drag manually: at drag start it snapshots each
panel's rectangle once (`capturePanelRects`) so per-move hit-testing does not
call `mapFromItem` over every panel, and the cursor ghost is rendered on its own
layer (`layer.enabled`) to keep dragging smooth.

## Hydrate (`SessionController._hydrate_chat`)

1. Return the live chat if already in `chat_manager`.
2. Load the stored dict off-thread (toast error if missing).
3. `_create_manager_chat` **on a worker thread** (`asyncio.to_thread`):
   normalize the stored `skills_config.activated` paths to forward slashes, then
   `load_skill_contents` (activated) + `load_tool_functions` (activated) +
   `build_tool_config`, resolve `model_name` (fallback to the config default),
   then `chat_manager.create_chat(...)` with the system prompt and `chat_limits`.
4. `await chat.refresh_estimated()` (offloaded); backfill `context_snapshot` and
   save off-thread if it was absent.
5. `ChatController.attach_worker(chat_id, agent)` then transfers ownership of the
   `Agent` (and its `messages`) to that chat's
   [`ChatWorker`](../modules/chat-worker.md) thread.

## Select model (`SkillDock` dropdown → `session._handle_model_changed`)

1. The dropdown lists `session.modelNames` and highlights
   `session.modelNameFor(activeChatId)`.
2. `_handle_model_changed(chat_id, name)` validates the name, writes
   `ChatState.model_name` and the stored record's `model_name`, calls
   `Agent.set_model` on the live agent (if present), and refreshes the panel so
   `ChatPanelModel.modelName` / `ConfigTokenBar` update.
3. Model changes apply to subsequent turns without recreating the chat.

## Persist (`ChatWorker._do_persist`)

The live chat's `Agent.messages` is owned by its worker thread, so the
[`ChatWorker`](../modules/chat-worker.md) persists the chat itself:

1. Load the stored record (one writer per chat file; atomic temp-file write).
2. `messages` = the agent's messages; `message_count`.
3. `context_snapshot` = `build_context_snapshot(agent)`.
4. `true_input_tokens` / `true_output_cum` from the worker's last `token_usage`.

The GUI never reads `Agent.messages`; `ChatState.message_count` and
`token_usage` signals keep panels and the sidebar in sync. Non-live chats are
edited directly through `ChatStore`.

## Delete chat (`ChatTabBar` × → `session._handle_delete_chat`)

1. `_forget_chat` — pop `ChatState`, stop the chat's worker (`remove_worker`),
   drop the live agent (`chat_manager.remove_chat`).
2. `ChatStore.delete_chat`; remove the chat from every panel (`_remove_chat_from_panels`).
3. Refresh; if the active chat was removed, open another panel's active chat.

## Delete session (`SessionSelector` × → `session._handle_delete_session`)

1. `ChatStore.delete_session(name)` deletes the session record **and its chats**.
2. `_forget_chat` each deleted chat; if it was active, fall back to `Default`.
3. Refresh → `_reconcile_panels` → `_sync_panels` → open the new panels.

## Layout persistence

Every layout mutation (`_handle_new_chat`, `_handle_panel_activate`,
`_handle_split`, `_handle_move_chat`, `_handle_delete_chat`, `_reconcile_panels`)
ends in `_save_layout`, which snapshots `{splits:[{chat_ids, active_chat_id}]}`
for the active session and queues a **debounced, off-thread** write through
`ChatStore.set_layout` (0.4 s quiet period, `asyncio.to_thread`). Rapid mutations
collapse into one write of the latest layout and a drop/move never blocks the GUI
on disk I/O. `ui.shutdown()` calls `session.flush_layout()` to persist any
still-pending layout synchronously before exit. On the next switch or app
restart, `_reconcile_panels` restores it.
