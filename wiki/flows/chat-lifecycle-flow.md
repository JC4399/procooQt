# Chat lifecycle flow

How sessions and chats are created, switched, laid out, hydrated, persisted, and
deleted.

Related: [`qt-session-controller`](../modules/qt-session-controller.md), [`qt-chat-state`](../modules/qt-chat-state.md), [`chat-manager`](../modules/chat-manager.md), [`chat-store`](../modules/chat-store.md).

## Entities

- A **session** is a named unit of work stored in `sessions.json` with a split
  layout (`splits: [{chat_ids, active_chat_id}]`, max 4). `Default` is created on
  first run.
- A **chat** is one conversation stored as `chats/<chat_id>.json` and carrying
  its own `session`, `skills_config`, `messages`, and `context_snapshot`.

```
(store)  --hydrate-->  (chat_manager / Agent)  <--live generation--
   │                        ▲                                    │
   │                        └───────── _save_current_chat_for ────┘
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
   `_apply_summaries` (seed per-chat counts, group chats by session, update the
   session menu, `_sync_panels`).
4. `_reconcile_panels(name)` reads the stored layout, keeps only chats that still
   exist, appends chats missing from the layout to the first panel, drops empty
   panels (min 1), and saves.
5. `_sync_panels()` pushes each panel's active chat, `ChatListModel`, tabs, and
   runtime into its `ChatPanelModel`, then calls `chat.set_visible_chats(...)`.
6. `_open_session_panels()` opens each panel's active chat (`_open_chat`:
   `chat_switch_started` → off-thread load/hydrate → `active_chat_changed`).

## Create chat (`ChatTabBar` `+` → `session._handle_new_chat(panel_index)`)

1. `_generate_unique_chat_id` — timestamp id, suffixed on collision.
2. `_create_stored_chat` → `ChatStore.save_chat` with `session` = the active
   session and empty `messages` / `skills_config`.
3. Append the id to that panel's tabs and set it active; refresh + save layout;
   `_open_chat`.
4. The skill dock later loads/persists real selections via the
   [config sync flow](config-sync-flow.md).

## Activate a tab (`ChatTabBar` click → `session._handle_panel_activate`)

Sets the panel's active chat, saves the layout, `_sync_panels`, and `_open_chat`.
`_open_chat` emits `chat_switch_started` (loading overlay), hydrates off-thread
if the chat isn't live, then emits `active_chat_changed`, which
`ChatController._handle_chat_activated` answers by rebuilding that chat's
transcript in batches behind the opaque loading overlay
(`_rebuild_chat_display_staged`, 400 ms minimum).

## Split / move (`SplitWorkspace` drag)

- **Split** (`_handle_split(chat_id, target_index, side)`): the target panel is
  kept (even if the dragged chat was its only tab) and a new panel is inserted
  left/right containing the chat. Max 4; the QML drop hint is suppressed at the
  limit.
- **Move** (`_handle_move_chat(chat_id, target_index)`): the chat is removed
  from its panel and appended to the target's tabs; empty source panels collapse.
- Both persist the layout and open the moved chat.

## Hydrate (`SessionController._hydrate_chat`)

1. Return the live chat if already in `chat_manager`.
2. Load the stored dict off-thread (toast error if missing).
3. `_create_manager_chat` **on a worker thread** (`asyncio.to_thread`):
   `load_skill_contents` (primary/secondary) + `load_tool_functions` (primary) +
   `build_tool_config`, then `chat_manager.create_chat(...)` with the system
   prompt and `chat_limits`. Agent construction and skill/AST loading therefore
   never block the GUI thread or the loading scanner.
4. `await chat.refresh_estimated()` (offloaded); backfill `context_snapshot`
   and save off-thread if it was absent.

## Persist (`SessionController._save_current_chat_for`)

1. Use the caller-provided `(messages, context_snapshot)` snapshot when given
   (captured on the GUI thread); otherwise capture one from the live chat.
2. `stored["messages"] = messages`; `message_count`.
3. `stored["context_snapshot"] = context_snapshot`.
4. `save_chat` (atomic temp-file write).

`_build_context_snapshot` captures `system_prompt`, `pending_additions`,
`primary_skills`, `secondary_skills`, `tools`, and `tool_config`.

## Delete chat (`ChatTabBar` × → `session._handle_delete_chat`)

1. `_forget_chat` — pop `ChatState`, cancel pending approval/generation,
   `chat_manager.remove_chat`.
2. `ChatStore.delete_chat`; remove the chat from every panel (`_remove_chat_from_panels`).
3. Refresh; if the active chat was removed, open another panel's active chat.

## Delete session (`SessionSelector` × → `session._handle_delete_session`)

1. `ChatStore.delete_session(name)` deletes the session record **and its chats**.
2. `_forget_chat` each deleted chat; if it was active, fall back to `Default`.
3. Refresh → `_reconcile_panels` → `_sync_panels` → open the new panels.

## Layout persistence

Every layout mutation (`_handle_new_chat`, `_handle_panel_activate`,
`_handle_split`, `_handle_move_chat`, `_handle_delete_chat`, `_reconcile_panels`)
ends in `_save_layout`, which writes `{splits:[{chat_ids, active_chat_id}]}` for
the active session through `ChatStore.set_layout`. On the next switch or app
restart, `_reconcile_panels` restores it.
