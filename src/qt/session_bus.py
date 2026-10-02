"""``SessionBus`` — broadcast hub for session-list changes across windows.

Every Procoo window owns a private :class:`~src.qt.session_controller.SessionController`
and therefore a private session-menu model. The bus is a single shared ``QObject``
that those controllers subscribe to, so a create or delete performed anywhere
(the control server or an in-app title bar) refreshes every open window's
title-bar session list at once.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SessionBus(QObject):
    """Broadcast hub signalling that the set of sessions changed.

    Attributes:
        sessions_changed: Emitted after any session is created or deleted.
    """

    sessions_changed = Signal()

    # ------------------------------------------------------------------
    #  Slot: Notify
    # ------------------------------------------------------------------

    def notify_changed(self) -> None:
        """Broadcast that the session list changed to every subscriber."""
        self.sessions_changed.emit()