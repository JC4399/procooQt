# qt.chat_panel_model — per-panel view model

Source: `src/qt/chat_panel_model.py`

## Purpose

One `ChatPanelModel` per visible split panel. It exposes the panel's active
chat, its tab model, and the runtime values QML binds to, so up to four panels
render and interact independently. `SessionController` owns and updates these
objects; QML reads them through `session.panelAt(index)`.

## Deliverables

- `ChatPanelModel(QObject)` with:
  - `panelIndex` (constant) — position in the workspace.
  - `activeChatId`, `chatModel`, `tabModel` — the panel's chat and tabs.
  - `busy`, `approvalVisible`, `approvalText`, `loading` — per-chat runtime.
  - `inputTokens`, `outputTokens` — live true token accounting (no estimate).
  - `primaryCount`, `allowCount`, `askCount`, `blockCount` — config summary.
  - `modelName` — LLM model selected for the active chat.
- `set_panel(...)` and `set_runtime(...)` mutators used by `SessionController`.

## Signals

| Signal | Meaning |
|---|---|
| `changed` | Any property changed (used as the notify for every property) |

## Properties

| Property | Type | Meaning |
|---|---|---|
| `panelIndex` | `int` | Position in the workspace (constant) |
| `activeChatId` | `str` | The panel's active chat id (or `""`) |
| `chatModel` | `QObject \| None` | `ChatListModel` for the active chat |
| `tabModel` | `ChatTabModel` | The panel's chat tabs |
| `busy` | `bool` | Active chat generating |
| `approvalVisible` / `approvalText` | `bool` / `str` | Pending tool approval |
| `inputTokens` / `outputTokens` | `int` | Context / cumulative output tokens |
| `loading` | `bool` | Switch-rebuild overlay showing |
| `primaryCount` / `allowCount` / `askCount` / `blockCount` | `int` | Skill/tool counts for the active chat |
| `modelName` | `str` | LLM model name for the active chat |

## Steps / Flow

- `SessionController._sync_panels` calls `set_panel(active_chat_id, chat_model,
  tabs, tabs_active_id, states)` then `set_runtime(...)` for each panel.
- `SessionController.refresh_chat_panels(chat_id)` (driven by
  `ChatController.chat_state_changed`) updates only the panel whose active chat
  changed.
- Both setters emit `changed`, so QML rebinds all panel properties.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, index: int, parent: QObject \| None = None) -> None` | panel index; parent | `None` | init fields + `ChatTabModel` | — |
| `def set_panel(self, active_chat_id, chat_model, tabs, tabs_active_id, states) -> None` | active chat, model, tab summaries, active tab id, states | `None` | store active chat/model → `tab_model.set_chats(...)` → emit `changed` | Resets tab model |
| `def set_runtime(self, busy, approval_visible, approval_text, input_tokens, output_tokens, loading, primary_count, allow_count, ask_count, block_count, model_name) -> None` | 11 runtime values | `None` | store all → emit `changed` | — |
