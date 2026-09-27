"""Pydantic data models for notifications."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class NotificationKind(StrEnum):
    """Notification category, mapped to a badge/card colour in the UI."""

    LOG = "log"
    INFO = "info"
    ERROR = "error"


class NotificationItem(BaseModel):
    """A single automation-run notification.

    Attributes:
        id: Unique notification identifier.
        kind: Category (``log`` for success runs, ``info``, or ``error``).
        task: Display name of the automation that ran.
        path: Relative automation path (used to open the editor on Debug).
        message: User-facing result message.
        log: Detailed run log (stdout/stderr + context log).
        data: Optional structured result data.
        timestamp: Completion time as ``"%Y-%m-%d %H:%M:%S"``.
        read: Whether the user has acknowledged the notification.
    """

    id: str
    kind: NotificationKind
    task: str
    path: str
    message: str
    log: str = ""
    data: Any = None
    timestamp: str = ""
    read: bool = False
