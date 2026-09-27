# Notification lifecycle flow

How an automation result reaches the title-bar badges and the notification pages.

Related: [notification](../modules/notification.md), [qt-notification-controller](../modules/qt-notification-controller.md), [automation-run-flow](automation-run-flow.md).

## 1. Result → notification

`AutomationController._on_result(result)` emits `result_ready`
(`Signal(object)`). `ProcooQtUI` wires `automation.result_ready →
notification._handle_automation_result`, which calls
`NotificationManager.add(result)` (mapping `success→log`, `info→info`,
`error→error`), rebuilds the notification-page model, reloads history, and emits
`counts_changed`.

## 2. Badges

The title bar reads `notification.logCount` / `infoCount` / `errorCount`.
`TitleBar.qml` renders one circular badge per non-zero count next to the
Notification tab (grey / amber / red); zero counts are hidden. Counts refresh
whenever `counts_changed` is emitted.

## 3. Reading a notification

| Kind | Read when | Card action |
|---|---|---|
| `log` | The notification page is shown (`NotificationPanel.onVisibleChanged`) | none |
| `info` | User presses **Confirm** | Confirm |
| `error` | User presses **Confirm** | Confirm, Debug |

- Page shown → `notification._handle_page_opened()` → `mark_logs_read()`.
- Confirm → `_handle_confirm(id)` → `mark_read(id)`.
- Debug → `_handle_debug(id)` → emits `edit_automation_requested(path)` →
  `EditorController._handle_open_automation(path)`, which emits
  `editor_open_requested` (QML shows the editor window) and loads
  `capabilities/automations/<path>/AUTOMATION.py`.

## 4. History

`NotificationPanel` shows all notifications (newest first) with a **View
history** button. `_handle_view_history()` resets the search and reloads page 0;
`NotificationHistoryWindow.qml` lists `history_model` and calls
`_handle_load_more()` when scrolled to the bottom (20 rows per page). Searching
calls `_handle_history_search(text)`, which resets to page 0.

## Persistence

`NotificationManager` writes `storage/notifications.json` on every mutation
(add, mark read), so history and read flags survive restarts. The manager is
Qt-free; the controller owns all UI signals.
