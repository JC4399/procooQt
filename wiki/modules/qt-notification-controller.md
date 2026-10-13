# qt.notification_controller — notification page, badges & history

Source: `src/qt/notification_controller.py`

## Purpose

Owns the notification UI state: the notification-page model, the per-kind unread
counts shown as title-bar badges, read semantics, the Debug action that opens the
source automation, and the searchable paged history window. It calls the Qt-free
[notification manager](notification.md) and emits the UI signals.

Read rules (see [notification-lifecycle-flow](../flows/notification-lifecycle-flow.md)):

- **log** — all logs are marked read when the notification page opens; they stay
  listed (rendered dimmed) until the page closes.
- **info / error** — marked read only when the user presses **Confirm**.
- **error** additionally offers **Debug**, which emits `edit_automation_requested`.

The bell page shows **unread** notifications, plus the success logs that the
current page-open just marked read; a read item disappears from the page once it
is closed (it stays in history).

## Deliverables

- `NotificationListModel` for the page (`notification_model`) and history
  (`history_model`).
- Count properties: `logCount`, `infoCount`, `errorCount`.
- History: `historySearch`, `historyExhausted`, `_handle_load_more`,
  `_handle_history_search`, `_handle_view_history`.
- Signals: `notifications_changed`, `counts_changed`, `history_changed`,
  `edit_automation_requested`.

## Signals & properties

| Signal | Payload | Emitted when |
|---|---|---|
| `notifications_changed` | — | Bell-page model rebuilt. |
| `counts_changed` | — | Unread counts changed (badges). |
| `history_changed` | — | History model/page/search changed. |
| `edit_automation_requested` | `str` | Debug pressed; payload is the automation path. |

| Property | Type | Notify | Meaning |
|---|---|---|---|
| `notification_model` | `QObject` | `notifications_changed` | Bell-page cards. |
| `history_model` | `QObject` | `history_changed` | History cards. |
| `logCount` / `infoCount` / `errorCount` | `int` | `counts_changed` | Unread counts per kind. |
| `historySearch` | `str` | `history_changed` | Active history filter. |
| `historyExhausted` | `bool` | `history_changed` | All matches loaded. |

## Steps / Flow

- `_handle_automation_result(result)` → `manager.add(result)` → rebuild page +
  reload history + emit counts.
- `_handle_page_opened()` → `_page_log_ids = set(manager.mark_logs_read())` →
  emit counts when non-empty → rebuild (keeps the just-read logs) + reload history.
- `_handle_page_closed()` → clear `_page_log_ids` → rebuild (unread only).
- `_handle_confirm(id)` → `manager.mark_read(id)`; if changed, rebuild.
- `_handle_debug(id)` → `manager.get(id)` → emit `edit_automation_requested(path)`.
- `_handle_load_more()` → next `HISTORY_PAGE_SIZE` (20) rows appended.
- `_handle_view_history()` / `_handle_history_search(text)` → reset to page 0.

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, app, parent=None) -> None` | app; parent | `None` | store app | — |
| `def build(self) -> None` | — | `None` | create models; rebuild page + history | — |
| `@Slot(object) def _handle_automation_result(self, result) -> None` | `AutomationResult` | `None` | add; rebuild; counts | Persists notification |
| `@Slot() def _handle_page_opened(self) -> None` | — | `None` | set `_page_log_ids`; mark logs read; rebuild + reload | Persists when changed |
| `@Slot() def _handle_page_closed(self) -> None` | — | `None` | clear `_page_log_ids`; rebuild | Emits `notifications_changed` |
| `@Slot(str) def _handle_confirm(self, item_id) -> None` | id | `None` | mark read | Persists when changed |
| `@Slot(str) def _handle_debug(self, item_id) -> None` | id | `None` | emit edit request | — |
| `@Slot() def _handle_view_history(self) -> None` | — | `None` | reset search + reload | Emits `history_changed` |
| `@Slot(str) def _handle_history_search(self, text) -> None` | text | `None` | reset + reload | Emits `history_changed` |
| `@Slot() def _handle_load_more(self) -> None` | — | `None` | append next page | Emits `history_changed` |
| `_unread(kind)` / `_rebuild_page()` / `_reload_history()` | — | int / `None` | helpers; page rebuild keeps unread + (while open) just-read logs | — |

## See also

- [notification](notification.md) — models/store/manager.
- [qt-models](qt-models.md) — `NotificationListModel`.
- [qt-editor-controller](qt-editor-controller.md) — where Debug opens files.
- [qt-ui](qt-ui.md) — composition.
