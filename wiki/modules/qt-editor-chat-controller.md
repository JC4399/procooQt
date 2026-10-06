# qt.editor_chat_controller — editor chat panel

Source: `src/qt/editor_chat_controller.py`

## Purpose

Backs the editor window's right-side chat panel (`EditorChatPanel.qml`). Unlike a
simplified text box, the editor chat is a **real chat** managed by
[`ChatController`](qt-chat-controller.md) under a private chat id
(`"editor-chat"`), so it renders the same streaming cards, tool cards, token bar,
and input as a workspace panel. This controller is a thin façade: it creates a
private chat record, marks the chat always-visible, injects the open file as
context, and exposes the per-chat state to QML.

The chat record uses a private session name (`__editor__`) so it never appears in
the session selector or workspace panels. Its skills/tools are copied from the
active chat with all tool modes forced to `allow` because the editor has no
approval bar.

## Deliverables

- A private chat (`EDITOR_CHAT_ID = "editor-chat"`, session `__editor__`) in
  `ChatStore`/`chat_manager`.
- `chat_model` (the `ChatController` `ChatListModel`), plus `busy`,
  `inputTokens`, `outputTokens`, `modelName`, config-count properties, and
  `approvalVisible` / `approvalText`.
- Slots `_handle_send`, `_handle_stop`, `_handle_regenerate`,
  `_handle_delete_turn`, `_handle_regenerate_from`, `_handle_clear`.
- File-context injection (`_file_context`), refreshed whenever the open file or
  its content changes.
- `state_changed` signal (from `chat.chat_state_changed` / `token_counts_changed`).
- The QML panel mirrors `ChatPanel.qml`: the same streaming cards, `AutoScrollToggle`,
  `ConfigTokenBar`, tool-approval bar, and the per-chat `SkillDock` (bound to
  `"editor-chat"`). The input row likewise uses `ScrollBar.AlwaysOff` (no right-side
  bar) and a hover-revealed `FlatCheckBox` enter lock that suppresses Enter-to-send
  while checked.

## Steps / Flow

### Build (`build`)

Create the private chat record if missing; `chat.add_visible_chat(chat_id)` so
`ChatController`'s visibility gate paints streaming cards; refresh.

### Send (`_handle_send` → `_send`)

1. `_ensure_chat_record()` (refreshes skills/tools from the active chat while the
   agent is not yet live).
2. `await session._hydrate_chat(chat_id)` builds/reuses the live `Agent`.
3. `_file_context()` returns an `[Editor context]` block (path + up to 8000
   chars) when the open file/content changed; appended as a system message.
4. `chat._handle_send_for(chat_id, message)` runs the normal generation loop —
   user card, streaming thinking/response/tool cards, persistence.

### Clear (`_handle_clear`)

Stop generation, drop the live agent, rewrite the chat record with empty
messages and a fresh skills config, reset state, and clear the model.

### State refresh

`ProcooQtUI` wires `chat.chat_state_changed → _handle_state_changed` and
`chat.token_counts_changed → _handle_token_counts`; both emit `state_changed`
so QML re-reads the properties from the chat's `ChatState`.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app, parent=None) -> None` | app; parent | `None` | store app | — |
| `def build(self) -> None` | — | `None` | create record; `chat.add_visible_chat`; refresh | Writes `chats/editor-chat.json` |
| `@Slot(str) def _handle_send(self, text) -> None` | text | `None` | validate; spawn `_send` | Toast when busy |
| `async def _send(self, message) -> None` | message | `None` | hydrate → inject context → `chat._handle_send_for` | Launches generation |
| `@Slot() def _handle_stop(self) -> None` | — | `None` | `chat._handle_stop_for` | — |
| `@Slot() def _handle_regenerate(self) -> None` | — | `None` | `chat._handle_regenerate_for` | — |
| `@Slot(int) def _handle_delete_turn(self, msg_index) -> None` | source message index | `None` | `chat._handle_delete_turn_for(chat_id, msg_index)` | Removes the card's message object |
| `@Slot(int) def _handle_regenerate_from(self, msg_index) -> None` | source user index | `None` | `chat._handle_regenerate_from_for(chat_id, msg_index)` | Truncates + regenerates |
| `@Slot() def _handle_clear(self) -> None` | — | `None` | stop; drop agent; reset record/model | Rewrites chat file |
| `@Slot(str) def _handle_state_changed(self, chat_id) -> None` | chat id | `None` | refresh if it is the editor chat | Emits `state_changed` |
| `_ensure_chat_record()` / `_active_skill_config()` | — | — / dict | create/refresh record; active skills forced allow | — |
| `_file_context(self) -> str` | — | context block or `""` | read open file once per change | — |

## See also

- [qt-chat-controller](qt-chat-controller.md) — owns the actual chat runtime/model.
- [qt-editor-controller](qt-editor-controller.md) — supplies the open file + tree.
- [qt-models](qt-models.md) — `ChatListModel` drives the cards.
- [qt-ui](qt-ui.md) — composition + context property `editorChat`.
