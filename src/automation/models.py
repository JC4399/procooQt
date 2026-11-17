"""Pydantic data models for automations and their execution results."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


def parse_iso_date(value: str) -> date | None:
    """Parse a ``YYYY-MM-DD`` string into a date.

    Args:
        value: The raw date string (leading/trailing whitespace allowed).

    Returns:
        The parsed date, or ``None`` when *value* is empty or malformed.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


class ActivationType(StrEnum):
    """How an automation is triggered."""

    SCHEDULED = "scheduled"
    EVENT = "event"


class AutomationResultKind(StrEnum):
    """Outcome category of an automation run.

    ``log`` / ``info`` / ``error`` map to a notification colour; ``silent``
    finishes without producing any notification.
    """

    LOG = "log"
    INFO = "info"
    ERROR = "error"
    SILENT = "silent"


class AutomationInfo(BaseModel):
    """Summary metadata for a discovered automation.

    Attributes:
        name: Human-readable automation name (from ``AUTOMATION.py`` frontmatter).
        path: Relative path from ``automations_dir`` (e.g. ``"reports/daily"``).
        directory: Absolute path to the automation folder.
        description: Short description of what the automation does.
        activation: Trigger type — ``scheduled`` or ``event``.
        schedule: Cron expression (``activation == scheduled``).
        event: Event name (``activation == event``).
        activated_skills: Optional skill paths fed to the automation's agent.
        has_scripts: Whether the folder contains a ``scripts/`` subdirectory.
        has_references: Whether the folder contains a ``references/`` subdirectory.
        enabled: Whether the automation is currently enabled (from state store).
        last_run: Timestamp of the most recent run, or an empty string.
        start_date: Optional first day the automation may fire (``YYYY-MM-DD``).
        end_date: Optional last day the automation may fire (``YYYY-MM-DD``).
    """

    name: str
    path: str
    directory: str
    description: str
    activation: ActivationType
    schedule: str = ""
    event: str = ""
    activated_skills: list[str] = []
    has_scripts: bool = False
    has_references: bool = False
    enabled: bool = True
    last_run: str = ""
    start_date: str = ""
    end_date: str = ""


class AutomationResult(BaseModel):
    """Normalised outcome of a single automation run.

    Attributes:
        kind: Outcome category used to colour the notification.
        path: Relative path of the automation that ran.
        task: Display name of the automation.
        message: User-facing result message (or error brief).
        log: Captured stdout/stderr run log.
        data: Optional structured result data.
        timestamp: Completion time as ``"%Y-%m-%d %H:%M:%S"``.
    """

    kind: AutomationResultKind
    path: str
    task: str
    message: str
    log: str = ""
    data: Any = None
    timestamp: str = ""
