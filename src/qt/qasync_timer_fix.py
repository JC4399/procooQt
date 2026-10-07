"""Runtime workaround for a Qt timer-handle leak in qasync 0.28.0.

qasync schedules every asyncio timer through ``_SimpleTimer``, which starts one
``QObject`` timer per callback and only calls ``killTimer`` when that timer
actually fires. A callback cancelled before its deadline therefore leaves its
Win32 USER timer alive for the full remaining deadline.

The OpenAI/httpx streaming path hits this hard: httpcore wraps every HTTP read
in ``anyio.fail_after(read_timeout)``, and the OpenAI client's default timeout is
600 seconds. Each streamed chunk schedules a 600 s deadline and cancels it as
soon as the chunk arrives, so each chunk leaks a USER timer for ~10 minutes.
Enough chunks exhaust the per-process USER-handle allowance; after that
``QEventDispatcherWin32::registerTimer`` fails and every QML ``Timer`` /
animation (streaming spinners, cursor blink, tab blink) silently stops, which
freezes the chat UI.

This module patches ``_SimpleTimer`` in memory so cancelling a callback also
kills its Qt timer immediately. It never edits the installed package.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("procoo_qt")

_INSTALLED = False


# ------------------------------------------------------------------
#  Cancel-aware handle proxy
# ------------------------------------------------------------------


class _CancelAwareHandle:
    """Forwarding proxy around an ``asyncio.Handle`` that frees its Qt timer.

    ``asyncio.Handle`` declares ``__slots__``, so attributes cannot be attached
    to it directly. This proxy forwards every attribute access to the wrapped
    handle and overrides :meth:`cancel` to release the underlying Qt timer at
    the moment of cancellation instead of waiting for the deadline to fire.
    """

    __slots__ = ("_handle", "_timer", "_timer_id")

    def __init__(self, handle: asyncio.Handle, timer: Any, timer_id: int) -> None:
        """Wrap an asyncio handle together with its Qt timer registration.

        Args:
            handle: The real asyncio handle to delegate to.
            timer: The ``_SimpleTimer`` instance owning the Qt timer.
            timer_id: The Qt timer id returned by ``startTimer``.
        """
        self._handle = handle
        self._timer = timer
        self._timer_id = timer_id

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the wrapped handle.

        Args:
            name: The attribute name.

        Returns:
            The wrapped handle's attribute (e.g. ``_run``, ``_cancelled``).
        """
        return getattr(self._handle, name)

    def cancel(self) -> None:
        """Cancel the callback and free its Qt timer immediately."""
        self._handle.cancel()
        timer = self._timer
        if timer is not None:
            timer._release(self._timer_id, self)
            self._timer = None


# ------------------------------------------------------------------
#  Installation
# ------------------------------------------------------------------


def install_qasync_timer_patch() -> None:
    """Patch qasync's ``_SimpleTimer`` to free Qt timers on cancellation.

    Idempotent: repeated calls are no-ops. Must be called before the
    ``qasync.QEventLoop`` is created.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    import qasync

    timer_cls: Any = qasync._SimpleTimer

    def add_callback(self: Any, handle: asyncio.Handle, delay: float = 0) -> _CancelAwareHandle:
        """Register a callback, returning a proxy that frees its timer on cancel.

        Args:
            self: The ``_SimpleTimer`` instance.
            handle: The asyncio handle to schedule.
            delay: Delay in seconds before the callback fires.

        Returns:
            The cancel-aware proxy wrapping ``handle``.
        """
        timer_id = self.startTimer(int(max(0, delay) * 1000))
        proxy = _CancelAwareHandle(handle, self, timer_id)
        callbacks = self._SimpleTimer__callbacks
        callbacks[timer_id] = proxy
        return proxy

    def _release(self: Any, timer_id: int, proxy: _CancelAwareHandle) -> None:
        """Kill a Qt timer if it is still owned by ``proxy``.

        Args:
            self: The ``_SimpleTimer`` instance.
            timer_id: The Qt timer id to release.
            proxy: The proxy whose registration is being released.
        """
        callbacks = self._SimpleTimer__callbacks
        if callbacks.get(timer_id) is proxy:
            del callbacks[timer_id]
            self.killTimer(timer_id)

    timer_cls.add_callback = add_callback
    timer_cls._release = _release
    _INSTALLED = True
    logger.info("Installed qasync Qt-timer leak patch")
