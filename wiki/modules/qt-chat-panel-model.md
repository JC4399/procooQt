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
- `set_panel(...)`, `set_runtime(...)`, `set_tokens(...)`, and `update_tab(...)`
  mutators used by `SessionController`.

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
  `ChatController.chat_state_changed`) updates the tab dot's status/blink via
  `update_tab(...)` in every panel that owns the chat, and refreshes the runtime
  values of the panel currently showing it.
- `SessionController.refresh_chat_tokens(chat_id)` (driven by
  `ChatController.chat_tokens_changed`) calls `set_tokens(...)` on the panel
  showing the chat, so the token bar updates on every `token_usage` event
  (each LLM round-trip, including tool-call rounds) without rebuilding the rest
  of the runtime state.
- `set_panel`, `set_runtime`, and `set_tokens` emit `changed`, so QML rebinds
  the affected panel properties; `update_tab` emits only the tab model's
  role-scoped `dataChanged` so the tab delegate (and its blink animation) is not
  recreated.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, index: int, parent: QObject \| None = None) -> None` | panel index; parent | `None` | init fields + `ChatTabModel` | — |
| `def set_panel(self, active_chat_id, chat_model, tabs, tabs_active_id, states) -> None` | active chat, model, tab summaries, active tab id, states | `None` | store active chat/model → `tab_model.set_chats(...)` → emit `changed` | Resets tab model |
| `def set_runtime(self, busy, approval_visible, approval_text, input_tokens, output_tokens, loading, primary_count, allow_count, ask_count, block_count, model_name) -> None` | 11 runtime values | `None` | store all → emit `changed` | — |
| `def set_tokens(self, input_tokens: int, output_tokens: int) -> None` | input/output tokens | `None` | dedupe → store → emit `changed` | Token-bar-only refresh (no full runtime rebuild) |
| `def update_tab(self, chat_id: str, status: str, blinking: bool) -> None` | chat, `ChatStatus`, blink flag | `None` | `tab_model.update_chat(...)` | Role-scoped `dataChanged` only; no panel rebuild |
