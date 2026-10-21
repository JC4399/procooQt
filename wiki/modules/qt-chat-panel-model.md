# qt.chat_panel_model — per-panel view model

Source: `src/qt/chat_panel_model.py`

## Purpose

One `ChatPanelModel` per panel **slot** (`SessionController.MAX_PANELS = 4`). It
exposes the panel's active chat, its tab model, and the runtime values QML binds
to, so up to four panels render and interact independently. `SessionController`
owns and updates these objects; QML reads them through `session.panelAt(slot)`.
Slots are fixed, so a panel keeps its model object as it moves, and QML never
rebuilds a panel delegate that only changed position.

## Deliverables

- `ChatPanelModel(QObject)` with:
  - `panelIndex` (constant) — the panel's fixed workspace slot id.
  - `activeChatId`, `chatModel`, `tabModel` — the panel's chat and tabs.
  - `busy`, `approvalVisible`, `approvalText`, `loading` — per-chat runtime.
  - `inputTokens`, `outputTokens` — live true token accounting (no estimate).
  - `activatedCount`, `allowCount`, `askCount`, `blockCount` — config summary.
  - `modelName` — LLM model selected for the active chat.
- `set_panel(...)`, `set_runtime(...)`, `set_tokens(...)`, and `update_tab(...)`
  mutators used by `SessionController`.

## Signals

| Signal | Meaning |
|---|---|
| `active_chat_changed` | The active chat id changed (notify for `activeChatId`) |
| `chat_model_changed` | The active chat's `ChatListModel` pointer changed (notify for `chatModel`) |
| `runtime_changed` | Any runtime display value changed (notify for `busy`, `approval*`, tokens, `loading`, counts, `modelName`) |

The three signals are split so a runtime-only update (e.g. a token tick) does not
invalidate the `chatModel`/`activeChatId` bindings, and so an untouched panel is
not invalidated by another panel's refresh.

## Properties

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `panelIndex` | `int` | constant | Fixed workspace slot id |
| `activeChatId` | `str` | `active_chat_changed` | The panel's active chat id (or `""`) |
| `chatModel` | `QObject \| None` | `chat_model_changed` | `ChatListModel` for the active chat |
| `tabModel` | `ChatTabModel` | constant | The panel's chat tabs (never reassigned) |
| `busy` | `bool` | `runtime_changed` | Active chat generating |
| `approvalVisible` / `approvalText` | `bool` / `str` | `runtime_changed` | Pending tool approval |
| `inputTokens` / `outputTokens` | `int` | `runtime_changed` | Context / cumulative output tokens |
| `loading` | `bool` | `runtime_changed` | Switch-rebuild overlay showing |
| `activatedCount` / `allowCount` / `askCount` / `blockCount` | `int` | `runtime_changed` | Skill/tool counts for the active chat |
| `modelName` | `str` | `runtime_changed` | LLM model name for the active chat |

## Steps / Flow

- `SessionController._sync_panels` calls `set_panel(active_chat_id, chat_model,
  tabs, tabs_active_id, states)` then `set_runtime(...)` for each panel. Both
  setters are compare-and-emit: an unchanged panel emits nothing, so a refresh
  driven by one chat does not disturb the other panels.
- `SessionController.refresh_chat_panels(chat_id)` (driven by
  `ChatController.chat_state_changed`) updates the tab dot's status/blink via
  `update_tab(...)` in every panel that owns the chat, and refreshes the runtime
  values of the panel currently showing it.
- `SessionController.refresh_chat_tokens(chat_id)` (driven by
  `ChatController.chat_tokens_changed`) calls `set_tokens(...)` on the panel
  showing the chat, so the token bar updates on every `token_usage` event
  (each LLM round-trip, including tool-call rounds) without rebuilding the rest
  of the runtime state.
- `set_panel` emits `active_chat_changed` / `chat_model_changed` only when those
  values actually change; `set_runtime`/`set_tokens` emit `runtime_changed` only
  when a value differs. `update_tab` emits only the tab model's role-scoped
  `dataChanged` so the tab delegate (and its blink animation) is not recreated.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, index: int, parent: QObject \| None = None) -> None` | panel slot; parent | `None` | init fields + `ChatTabModel` | — |
| `def set_panel(self, active_chat_id, chat_model, tabs, tabs_active_id, states) -> None` | active chat, model, tab summaries, active tab id, states | `None` | compare active/model → store → `tab_model.set_chats(...)` (incremental) → emit `active_chat_changed`/`chat_model_changed` only on change | No-op when unchanged; tab model self-dedupes |
| `def set_runtime(self, busy, approval_visible, approval_text, input_tokens, output_tokens, loading, activated_count, allow_count, ask_count, block_count, model_name) -> None` | 11 runtime values | `None` | compare all → store → emit `runtime_changed` | No-op when unchanged |
| `def set_tokens(self, input_tokens: int, output_tokens: int) -> None` | input/output tokens | `None` | dedupe → store → emit `runtime_changed` | Token-bar-only refresh (no full runtime rebuild) |
| `def update_tab(self, chat_id: str, status: str, blinking: bool) -> None` | chat, `ChatStatus`, blink flag | `None` | `tab_model.update_chat(...)` | Role-scoped `dataChanged` only; no panel rebuild |
