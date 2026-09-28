"""Windows-native frame integration for the frameless main window.

``Qt.FramelessWindowHint`` strips the native ``WS_CAPTION`` / ``WS_THICKFRAME``
styles, which removes native edge resizing and Windows Aero Snap. This module
re-adds those styles to the main window and then hides the native chrome by
answering ``WM_NCCALCSIZE`` with "the whole window is client area". Edge resize
is restored through ``WM_NCHITTEST`` and, because the window is a native caption
target again, the existing QML ``startSystemMove`` regains Aero Snap.

Everything here is a no-op on non-Windows platforms.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import sys
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtGui import QWindow

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

logger = logging.getLogger("procoo_qt")

_IS_WINDOWS = sys.platform == "win32"


# ------------------------------------------------------------------
#  Win32 constants
# ------------------------------------------------------------------

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_GETMINMAXINFO = 0x0024

GWL_STYLE = -16

WS_THICKFRAME = 0x00040000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

HTCLIENT = 1
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

MONITOR_DEFAULTTONEAREST = 2

#: Thickness of the draggable resize border in device-independent pixels.
RESIZE_BORDER = 6

#: Style bits re-added so Windows treats the window as resizable and snappable.
_FRAME_STYLE = WS_THICKFRAME | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX


# ------------------------------------------------------------------
#  Win32 structures
# ------------------------------------------------------------------


class _POINT(ctypes.Structure):
    """A Win32 ``POINT`` (two signed longs)."""

    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _RECT(ctypes.Structure):
    """A Win32 ``RECT`` (four signed longs)."""

    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _MSG(ctypes.Structure):
    """A Win32 ``MSG`` as delivered by the Windows event dispatcher."""

    _fields_ = [
        ("hWnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _POINT),
    ]


class _MINMAXINFO(ctypes.Structure):
    """A Win32 ``MINMAXINFO`` payload for ``WM_GETMINMAXINFO``."""

    _fields_ = [
        ("ptReserved", _POINT),
        ("ptMaxSize", _POINT),
        ("ptMaxPosition", _POINT),
        ("ptMinTrackSize", _POINT),
        ("ptMaxTrackSize", _POINT),
    ]


class _MONITORINFO(ctypes.Structure):
    """A Win32 ``MONITORINFO`` holding the monitor and work-area rectangles."""

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
    ]


# ------------------------------------------------------------------
#  Win32 function bindings
# ------------------------------------------------------------------

_user32: Any = ctypes.windll.user32 if _IS_WINDOWS else None
_GetWindowLongPtr: Any = None
_SetWindowLongPtr: Any = None

if _IS_WINDOWS:
    _GetWindowLongPtr = _user32.GetWindowLongPtrW
    _GetWindowLongPtr.restype = ctypes.c_ssize_t
    _GetWindowLongPtr.argtypes = (wintypes.HWND, ctypes.c_int)

    _SetWindowLongPtr = _user32.SetWindowLongPtrW
    _SetWindowLongPtr.restype = ctypes.c_ssize_t
    _SetWindowLongPtr.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)

    _user32.GetWindowRect.restype = wintypes.BOOL
    _user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(_RECT))

    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = (
        wintypes.HWND,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    )

    _user32.MonitorFromWindow.restype = ctypes.c_void_p
    _user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)

    _user32.GetMonitorInfoW.restype = wintypes.BOOL
    _user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.POINTER(_MONITORINFO))

    _user32.DefWindowProcW.restype = ctypes.c_ssize_t
    _user32.DefWindowProcW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------


def _event_name(event_type: Any) -> bytes:
    """Return the platform event name as raw bytes.

    Args:
        event_type: ``QByteArray`` or ``bytes`` supplied by Qt.

    Returns:
        The event name encoded as bytes.
    """
    data = getattr(event_type, "data", None)
    if callable(data):
        return bytes(data())
    return bytes(event_type)


def _point_from_lparam(lparam: int) -> tuple[int, int]:
    """Decode the packed signed screen coordinates from a ``WM_NCHITTEST`` ``lParam``.

    Args:
        lparam: The message ``lParam``.

    Returns:
        A ``(x, y)`` tuple in physical screen pixels.
    """
    x = ctypes.c_short(lparam & 0xFFFF).value
    y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
    return x, y


def _resize_hit_code(x: int, y: int, rect: _RECT, border: int) -> int:
    """Return the non-client hit code for a cursor position on the window frame.

    Args:
        x: Cursor x in physical screen pixels.
        y: Cursor y in physical screen pixels.
        rect: The window rectangle in physical screen pixels.
        border: The resize border thickness in physical pixels.

    Returns:
        One of the ``HT*`` hit codes, or ``HTCLIENT`` when the cursor is inside
        the client area.
    """
    on_left = x < rect.left + border
    on_right = x >= rect.right - border
    on_top = y < rect.top + border
    on_bottom = y >= rect.bottom - border

    if on_top and on_left:
        return HTTOPLEFT
    if on_top and on_right:
        return HTTOPRIGHT
    if on_bottom and on_left:
        return HTBOTTOMLEFT
    if on_bottom and on_right:
        return HTBOTTOMRIGHT
    if on_left:
        return HTLEFT
    if on_right:
        return HTRIGHT
    if on_top:
        return HTTOP
    if on_bottom:
        return HTBOTTOM
    return HTCLIENT


# ------------------------------------------------------------------
#  Native event filter
# ------------------------------------------------------------------


class FramelessNativeEventFilter(QAbstractNativeEventFilter):
    """Restores resize, shadow, and Aero Snap for one frameless top-level window.

    The filter answers ``WM_NCCALCSIZE`` so the native frame is never drawn,
    ``WM_NCHITTEST`` so the window borders resize natively, and
    ``WM_GETMINMAXINFO`` so a maximized window fills the monitor work area
    exactly instead of overhanging it.

    Attributes:
        _window: The Qt window whose native handle is managed.
        _hwnd: The native window handle, as an integer.
    """

    def __init__(self, window: QWindow) -> None:
        """Initialise the filter for a specific window.

        Args:
            window: The frameless window to manage.
        """
        super().__init__()
        self._window = window
        self._hwnd = int(window.winId())

    # ------------------------------------------------------------------
    #  Qt override
    # ------------------------------------------------------------------

    def nativeEventFilter(  # noqa: N802
        self, event_type: Any, message: Any
    ) -> tuple[bool, int]:
        """Handle the Windows messages that keep the window resizable and snappable.

        Args:
            event_type: The platform event name supplied by Qt.
            message: A pointer to the native ``MSG`` structure.

        Returns:
            ``(handled, result)`` where ``result`` becomes the ``LRESULT``.
        """
        if not _IS_WINDOWS or _event_name(event_type) != b"windows_generic_MSG":
            return False, 0

        msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
        if int(msg.hWnd or 0) != self._hwnd:
            return False, 0

        if msg.message == WM_NCCALCSIZE:
            return True, 0
        if msg.message == WM_NCHITTEST:
            return True, self._hit_test(int(msg.lParam))
        if msg.message == WM_GETMINMAXINFO:
            self._apply_work_area(msg)
            return True, 0
        return False, 0

    # ------------------------------------------------------------------
    #  Private
    # ------------------------------------------------------------------

    def _hit_test(self, lparam: int) -> int:
        """Return the non-client hit code for the current cursor position.

        Args:
            lparam: The ``WM_NCHITTEST`` message ``lParam``.

        Returns:
            A native ``HT*`` hit code.
        """
        if self._is_maximized():
            return HTCLIENT
        x, y = _point_from_lparam(lparam)
        rect = _RECT()
        _user32.GetWindowRect(self._hwnd, ctypes.byref(rect))
        border = max(1, round(RESIZE_BORDER * self._window.devicePixelRatio()))
        return _resize_hit_code(x, y, rect, border)

    def _apply_work_area(self, msg: _MSG) -> None:
        """Constrain the maximized size to the nearest monitor's work area.

        Args:
            msg: The ``WM_GETMINMAXINFO`` message.
        """
        _user32.DefWindowProcW(msg.hWnd, msg.message, msg.wParam, msg.lParam)
        monitor = _user32.MonitorFromWindow(msg.hWnd, MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return
        minmax = ctypes.cast(msg.lParam, ctypes.POINTER(_MINMAXINFO)).contents
        work = info.rcWork
        monitor_rect = info.rcMonitor
        minmax.ptMaxPosition.x = work.left - monitor_rect.left
        minmax.ptMaxPosition.y = work.top - monitor_rect.top
        minmax.ptMaxSize.x = work.right - work.left
        minmax.ptMaxSize.y = work.bottom - work.top

    def _is_maximized(self) -> bool:
        """Return whether the window is maximized or fullscreen.

        Returns:
            ``True`` when the window occupies a maximized or fullscreen state.
        """
        visibility = self._window.visibility()
        return visibility in (QWindow.Visibility.Maximized, QWindow.Visibility.FullScreen)


# ------------------------------------------------------------------
#  Installation
# ------------------------------------------------------------------


def enable_native_frame(window: QWindow) -> None:
    """Re-add the native resize/caption styles to a frameless window.

    Args:
        window: The frameless top-level window.
    """
    if not _IS_WINDOWS:
        return
    hwnd = int(window.winId())
    style = _GetWindowLongPtr(hwnd, GWL_STYLE)
    _SetWindowLongPtr(hwnd, GWL_STYLE, style | _FRAME_STYLE)
    _user32.SetWindowPos(
        hwnd,
        None,
        0,
        0,
        0,
        0,
        SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER,
    )


def install(qt_app: QApplication, window: QWindow) -> FramelessNativeEventFilter | None:
    """Install the frameless-window native event filter.

    The filter is installed before the native styles are enabled so the resulting
    ``WM_NCCALCSIZE`` recalculation is intercepted.

    Args:
        qt_app: The running application that receives native events.
        window: The frameless main window to manage.

    Returns:
        The installed filter (keep a reference for its lifetime), or ``None`` on
        non-Windows platforms.
    """
    if not _IS_WINDOWS:
        return None
    event_filter = FramelessNativeEventFilter(window)
    qt_app.installNativeEventFilter(event_filter)
    enable_native_frame(window)
    logger.info("Enabled native frame for main window (resize + Aero Snap)")
    return event_filter
