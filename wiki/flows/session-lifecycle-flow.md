# Session lifecycle flow

How sessions are created, switched, hydrated, persisted, and deleted.

Related: [`qt-session-controller`](../modules/qt-session-controller.md), [`qt-session-state`](../modules/qt-session-state.md), [`session-manager`](../modules/session-manager.md), [`session-store`](../modules/session-store.md).

## Lifecycle states

```
(store)  --hydrate-->  (session_manager / Agent)  <--live generation--
   │                        ▲                                    │
   │                        └───────── _save_current_session_for ┘
   ▼
(delete)  --remove-->  gone from store + manager + UI
```

`SessionController` owns the `session_ids` list, the `SessionState` registry,
and the active id; `ChatController` is notified of the active id through
`active_session_changed` and swaps to that session's `ChatListModel`.

## Create (`SessionPanel` → `session._handle_new_session`)

1. `_generate_unique_session_id` — timestamp id, suffixed on collision.
2. `_create_stored_session` → `SessionStore.save_session` with empty `messages`
   and `skills_config = {primary: [], secondary: [], tools: {}}`.
3. Prepend the id to `session_ids`; `_switch_to_session`.
4. The skill sidebar later loads/persists the real selections via the
   [config sync flow](config-sync-flow.md).

## Switch (`session._handle_session_click` → `_switch_to_session`)

1. Save the current session (persist messages + context snapshot).
2. Set `active_session_id`; create the `SessionState`; `_refresh_model`;
   emit `active_session_changed(session_id)`.
3. If there is no live session but stored messages exist →
   `await _hydrate_session`.
4. `ChatController._handle_session_activated` (connected to the signal) points
   `activeModel` at the session's model, resets render keys, shows the loading
   spinner, and schedules `_rebuild_after_switch`.

## Hydrate (`SessionController._hydrate_session`)

1. Return the live session if already in `session_manager`.
2. Load the stored dict (toast error if missing).
3. `_create_manager_session`: `load_skill_contents` (primary/secondary) +
   `load_tool_functions` (primary) + `build_tool_config`, then
   `session_manager.create_session(model, ..., initial_messages=stored["messages"])`
   with the system prompt and session limits.
4. `await session.refresh_estimated()`; backfill `context_snapshot` and save if
   it was absent.

## Persist (`SessionController._save_current_session_for`)

1. Get the live session; return if there is none.
2. `stored["messages"] = session.messages`; `message_count`.
3. `stored["context_snapshot"] = _build_context_snapshot(session)`.
4. `save_session`.

`_build_context_snapshot` captures `system_prompt`, `pending_additions`,
`primary_skills`, `secondary_skills`, `tools`, and `tool_config`.

## Delete (`session._handle_delete_session` → `_delete_session_by_id`)

1. Pop the `SessionState`; `_cancel_pending_operations` (deny a pending tool,
   set the approval event, cancel the active generation task).
2. `session_manager.remove_session`; `session_store.delete_session`.
3. Remove from `session_ids`; if it was active, switch to the next session,
   otherwise emit `active_session_changed("")` to clear the chat.

## Startup auto-select (`SessionController.start`)

1. `_emit_validation_issues` — surface skill ERROR/WARNING issues as toasts.
2. `_auto_select_session` picks the latest stored session (newest-first list)
   and switches to it, or creates a fresh timestamp session when none exist.

## Folders (`SessionPanel` → `session._handle_*`)

`_handle_create_folder` / `_handle_delete_folder` delegate to
`SessionStore.create_folder` / `delete_folder`; `_handle_drop_on_folder` sets a
session's folder (empty string = unfiled); `_handle_folder_expansion` toggles
the `SessionListModel` expansion state.
