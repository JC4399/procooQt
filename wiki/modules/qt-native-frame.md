# qt.native_frame — Windows native frame for the main window

Source: `src/qt/native_frame.py`

## Purpose

`Main.qml` is a frameless window (`Qt.FramelessWindowHint`), which strips the
native `WS_CAPTION` / `WS_THICKFRAME` styles. That removal costs native edge
resizing and Windows Aero Snap. This module re-adds those styles to the main
window and then hides the native chrome by answering `WM_NCCALCSIZE` with "the
whole window is client area". Edge resize is restored through `WM_NCHITTEST`,
and because the window is a native caption target again, the existing QML
`Window.startSystemMove()` regains Aero Snap.

Everything here is a no-op on non-Windows platforms.

## Deliverables

- `FramelessNativeEventFilter(QAbstractNativeEventFilter)` — answers the three
  Windows messages for one top-level window's native handle.
- `enable_native_frame(window)` — ORs the caption/resize styles back onto the
  frameless window and forces a frame recalculation.
- `install(qt_app, window)` — installs the filter and enables the styles,
  returning the filter (keep a reference for its lifetime).
- Win32 constants, ctypes `_POINT` / `_RECT` / `_MSG` / `_MINMAXINFO` /
  `_MONITORINFO` structs, and `user32` prototypes.
- Helpers `_event_name`, `_point_from_lparam`, `_resize_hit_code`.

## Steps / Flow

### `install` (from `app.main`)

1. On non-Windows, return `None` without touching anything.
2. Build `FramelessNativeEventFilter(window)`; it caches the integer `winId()`.
3. `qt_app.installNativeEventFilter(filter)`.
4. `enable_native_frame(window)`:
   - `GetWindowLongPtrW(GWL_STYLE)` → OR `WS_THICKFRAME | WS_CAPTION |
     WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX` → `SetWindowLongPtrW`.
   - `SetWindowPos(..., SWP_FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER)` to force
     a fresh `WM_NCCALCSIZE` (now intercepted because the filter is installed).
5. Log and return the filter so `app.main` can hold the only reference.

### `nativeEventFilter` message handling

Only `windows_generic_MSG` messages whose `hWnd` matches the cached handle are
handled.

| Message | Response | Effect |
|---|---|---|
| `WM_NCCALCSIZE` (0x0083) | `(True, 0)` | Client area = whole window; native chrome never drawn. |
| `WM_NCHITTEST` (0x0084) | `(True, HT*)` | Native 8-way edge/corner resize with system cursors. |
| `WM_GETMINMAXINFO` (0x0024) | `(True, 0)` | Maximized window fills the monitor work area exactly (no thick-frame overhang). |
| anything else | `(False, 0)` | Passed to Qt unchanged. |

`WM_NCHITTEST` returns `HTCLIENT` when the window is maximized/fullscreen, so a
maximized window cannot be drag-resized. Otherwise it measures the cursor
(decoded from the packed signed `lParam`) against `GetWindowRect` and returns the
matching `HT*` code inside a `RESIZE_BORDER`-thick border scaled by
`window.devicePixelRatio()`.

`WM_GETMINMAXINFO` first calls `DefWindowProcW` to fill the defaults, then
overrides `ptMaxPosition` / `ptMaxSize` from
`MonitorFromWindow(MONITOR_DEFAULTTONEAREST)` + `GetMonitorInfoW`.

## Function Reference

### `FramelessNativeEventFilter`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, window: QWindow) -> None` | `window` — the frameless main window | `None` | Caches `window` and `int(window.winId())` | Creates the native handle if not yet created |
| `def nativeEventFilter(self, event_type: Any, message: Any) -> tuple[bool, int]` | `event_type` — Qt platform event name; `message` — pointer to a native `MSG` | `(handled, lresult)` | Match `windows_generic_MSG` + `hWnd`; dispatch `WM_NCCALCSIZE` / `WM_NCHITTEST` / `WM_GETMINMAXINFO` | Writes to the native `MINMAXINFO` for `WM_GETMINMAXINFO` |
| `def _hit_test(self, lparam: int) -> int` | `lparam` — `WM_NCHITTEST` lParam | native `HT*` code | `HTCLIENT` if maximized; else decode cursor + `GetWindowRect` + `_resize_hit_code` | Calls `user32` |
| `def _apply_work_area(self, msg: _MSG) -> None` | `msg` — the `WM_GETMINMAXINFO` message | `None` | `DefWindowProcW` → monitor work area → set `ptMaxPosition` / `ptMaxSize` | Mutates the native `MINMAXINFO` |
| `def _is_maximized(self) -> bool` | — | `bool` | `window.visibility() in (Maximized, FullScreen)` | — |

### Module functions

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def enable_native_frame(window: QWindow) -> None` | `window` — frameless top-level window | `None` | OR frame styles via `SetWindowLongPtrW`; `SetWindowPos(SWP_FRAMECHANGED …)` | Mutates native window styles; no-op off-Windows |
| `def install(qt_app: QApplication, window: QWindow) -> FramelessNativeEventFilter \| None` | `qt_app` — running app; `window` — frameless main window | the filter, or `None` off-Windows | Filter → `installNativeEventFilter` → `enable_native_frame` → log | Installs a global native event filter; caller must keep the returned reference |

### Constants and helpers

| Name | Value / Type | Meaning |
|---|---|---|
| `WM_NCCALCSIZE` / `WM_NCHITTEST` / `WM_GETMINMAXINFO` | `0x0083` / `0x0084` / `0x0024` | Handled window messages |
| `WS_THICKFRAME` / `WS_CAPTION` / `WS_SYSMENU` / `WS_MINIMIZEBOX` / `WS_MAXIMIZEBOX` | `0x0004…` etc. | Styles re-added to the frameless window |
| `HTCLIENT` … `HTBOTTOMRIGHT` | `1`, `10`–`17` | Non-client hit-test results |
| `RESIZE_BORDER` | `6` | Resize border thickness in device-independent px |
| `_event_name(event_type) -> bytes` | helper | Normalises `QByteArray` / `bytes` event names |
| `_point_from_lparam(lparam) -> tuple[int, int]` | helper | Decodes signed screen coords from a packed `lParam` |
| `_resize_hit_code(x, y, rect, border) -> int` | helper | Maps a cursor position to an `HT*` code |

## See also

- [app](app.md) — installs the filter right after `Main.qml` loads.
- [qt-ui](qt-ui.md) — orchestrator; `Main.qml` / `TitleBar.qml` remain view-only.
