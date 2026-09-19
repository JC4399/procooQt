# qt.error_handler — error routing & toast notifications

Source: `src/qt/error_handler.py`

## Purpose

Route UI errors and warnings to QML toasts. Where the Flet edition pushed a
toast onto `page.overlay`, the Qt edition emits a `toast_requested` signal and a
QML `ToastHost` component renders it. Errors carry a short `brief` (shown in the
toast) and a `detail` (logged).

## Deliverables

- `ErrorNotifier(QObject)` — emits `toast_requested(message, level)`.
- Constants `TOAST_ERROR = "error"`, `TOAST_WARNING = "warning"`,
  `TOAST_INFO = "info"`.
- `show_error` / `show_warning` — request a toast at the given level.
- `handle_error(error, session=None)` — log and surface an exception.

## Steps / Flow

### `handle_error`

1. If `error` is a `ProcooError`: log `error.detail` at `ERROR` and toast
   `error.brief` at `TOAST_ERROR`.
2. Otherwise: `logger.exception("Unhandled UI error")` and toast `str(error)`.
3. If a `session` is given, push
   `{"type": "error", "brief": str(error), "detail": "", "category": "general"}`
   onto `session.event_queue`.

### ToastHost consumption (QML)

1. `ui.py` connects every controller's `toast_requested` signal to
   `self.notifier.toast_requested`, and exposes the notifier as the `toasts`
   context property (`context.setContextProperty("toasts", self.notifier)`).
2. `Main.qml` instantiates `ToastHost { notifier: toasts }`.
3. `ToastHost.qml` holds `property var notifier` and a `Connections` block whose
   `onToast_requested(message, level)` appends
   `{ "message": message, "level": level }` to its local `ListModel`.
4. A `Repeater`/`Rectangle` delegate colours the toast by `level`: `error` →
   `errorSnackbar` / `accentRed`, `info` → `surfaceBg` / `accentGreen`, anything
   else (`warning`) → `warningSnackbar` / `accentAmber`.
5. A 5-second `Timer` removes the toast from the model.

## Function Reference

### `show_error` / `show_warning`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def show_error(self, message: str) -> None` | `message` — display text | `None` | `toast_requested.emit(message, TOAST_ERROR)` | Emits signal |
| `def show_warning(self, message: str) -> None` | `message` — display text | `None` | `toast_requested.emit(message, TOAST_WARNING)` | Emits signal |

### `handle_error`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def handle_error(self, error: BaseException, session: Agent \| None = None) -> None` | `error` — exception; `session` — optional `Agent` | `None` | `ProcooError` → log `detail` + toast `brief`; else `logger.exception` + toast `str(error)`; then push to `session.event_queue` | Emits `toast_requested`; mutates `session.event_queue` when `session` is set |

### Signal and constants

| Name | Type / Value | Meaning |
|---|---|---|
| `ErrorNotifier.toast_requested` | `Signal(str, str)` | `(message, level)` |
| `TOAST_ERROR` | `"error"` | red toast |
| `TOAST_WARNING` | `"warning"` | amber toast |
| `TOAST_INFO` | `"info"` | neutral/green toast (used by controllers, e.g. editor save) |

## See also

- [qt-models](qt-models.md) — `SessionListModel` rows expose the same status
  vocabulary the toast levels mirror.
