"""Error routing and toast notifications for the Qt UI.

The controller emits a ``toast_requested`` signal and a QML ``Toast`` component renders
it. Errors carry a short ``brief`` (shown in the toast) and a ``detail`` (logged).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from ..util.error.types import ProcooError

if TYPE_CHECKING:
    from ..session.agent import Agent

logger = logging.getLogger("procoo_qt")

TOAST_ERROR = "error"
TOAST_WARNING = "warning"
TOAST_INFO = "info"


class ErrorNotifier(QObject):
    """Emits toast requests and logs errors for the QML layer."""

    #: ``(message, level)`` where level is ``"error"`` or ``"warning"``.
    toast_requested = Signal(str, str)

    # ------------------------------------------------------------------
    #  Public
    # ------------------------------------------------------------------

    def show_error(self, message: str) -> None:
        """Request an error toast.

        Args:
            message: The message to display.
        """
        self.toast_requested.emit(message, TOAST_ERROR)

    def show_warning(self, message: str) -> None:
        """Request a warning toast.

        Args:
            message: The message to display.
        """
        self.toast_requested.emit(message, TOAST_WARNING)

    def handle_error(self, error: BaseException, session: Agent | None = None) -> None:
        """Log an error and surface a toast.

        Args:
            error: The exception to handle.
            session: Optional session to push the error onto its event queue.
        """
        if isinstance(error, ProcooError):
            logger.error("%s", error.detail)
            self.show_error(error.brief)
        else:
            logger.exception("Unhandled UI error")
            self.show_error(str(error))
        if session is not None:
            session.event_queue.put_nowait(
                {"type": "error", "brief": str(error), "detail": "", "category": "general"},
            )
