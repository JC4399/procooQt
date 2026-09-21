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
3. Prepend the id to `session_ids`; emit `session_switch_started(id)`;
   `_switch_to_session`.
4. The skill sidebar later loads/persists the real selections via the
   [config sync flow](config-sync-flow.md).

## Switch (`session._handle_session_click` → `_switch_to_session`)

1. `_handle_session_click` emits `session_switch_started(session_id)`
   synchronously (also emitted on new/startup/delete). It is wired to
   `ChatController._handle_session_switch_started`, which turns on `loading`, so
   the chat overlay paints immediately — before any disk work.
2. Set `active_session_id`; create the `SessionState`.
3. Snapshot the previous session on the GUI thread, then save it on a worker
   thread: `await asyncio.to_thread(_save_current_session_for, old, snapshot)`.
4. Reload the sidebar off the GUI thread: `await
   asyncio.to_thread(_collect_summaries)` (one parse per file) →
   `_apply_summaries(...)` → emit `active_session_changed(session_id)`.
5. Load the target record off-thread; if there is no live session but stored
   messages exist → `await _hydrate_session`.
6. After each `await`, abort when `active_session_id` changed, so a newer switch
   supersedes an in-flight one.
7. `ChatController._handle_session_activated` (connected to the signal) points
   `activeModel` at the session's model, resets render keys, and schedules
   `_rebuild_after_switch`. The transcript is built in batches behind the opaque
   loading overlay in `ChatPanel.qml` (`_rebuild_chat_display_staged`): the
   render plan itself is computed on a worker thread, the partially-built list is
   never shown, the overlay's `KnightRiderSpinner` runs until the build completes
   (plus a 400 ms minimum), and when the overlay drops the view is pinned to the
   newest card at the bottom. A user action flushes the remaining rows
   immediately (`_skip_staged_build`); activating another session drops the build
   (`_cancel_staged_build`).

## Hydrate (`SessionController._hydrate_session`)

1. Return the live session if already in `session_manager`.
2. Load the stored dict off-thread (toast error if missing).
3. `_create_manager_session` **on a worker thread** (`asyncio.to_thread`):
   `load_skill_contents` (primary/secondary) + `load_tool_functions` (primary) +
   `build_tool_config`, then `session_manager.create_session(...)` (now
   synchronous) with the system prompt and session limits. Agent construction and
   skill/AST loading therefore never block the GUI thread or the loading scanner.
4. `await session.refresh_estimated()` (offloaded); backfill `context_snapshot`
   and save off-thread if it was absent.

## Persist (`SessionController._save_current_session_for`)

1. Use the caller-provided `(messages, context_snapshot)` snapshot when given
   (captured on the GUI thread); otherwise capture one from the live session and
   return if there is none.
2. `stored["messages"] = messages`; `message_count`.
3. `stored["context_snapshot"] = context_snapshot`.
4. `save_session` (atomic temp-file write).

`_build_context_snapshot` captures `system_prompt`, `pending_additions`,
`primary_skills`, `secondary_skills`, `tools`, and `tool_config`. Passing a
snapshot lets the file I/O run on a worker thread without serializing a message
list that is still being appended to.

## Delete (`session._handle_delete_session` → `_delete_session_by_id`)

1. Pop the `SessionState`; `_cancel_pending_operations` (deny a pending tool,
   set the approval event, cancel the active generation task).
2. `session_manager.remove_session`; `session_store.delete_session`.
3. Remove from `session_ids`; if it was active, emit
   `session_switch_started(next_id)` and switch to the next session, otherwise
   emit `active_session_changed("")` to clear the chat.

## Startup auto-select (`SessionController.start`)

1. `_emit_validation_issues` — surface skill ERROR/WARNING issues as toasts.
2. `_auto_select_session` picks the latest stored session (newest-first list)
   and switches to it (emitting `session_switch_started` first), or creates a
   fresh timestamp session when none exist.

## Folders (`SessionPanel` → `session._handle_*`)

`_handle_create_folder` / `_handle_delete_folder` delegate to
`SessionStore.create_folder` / `delete_folder`; `_handle_drop_on_folder` sets a
session's folder (empty string = unfiled); `_handle_folder_expansion` toggles
the `SessionListModel` expansion state.
