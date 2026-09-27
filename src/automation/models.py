"""Pydantic data models for automations and their execution results."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ActivationType(StrEnum):
    """How an automation is triggered."""

    SCHEDULED = "scheduled"
    EVENT = "event"


class AutomationResultKind(StrEnum):
    """Outcome category of an automation run, mapped to a notification colour."""

    SUCCESS = "success"
    INFO = "info"
    ERROR = "error"


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
        primary_skills: Optional skill paths fed to the automation's agent.
        secondary_skills: Optional secondary skill paths.
        has_scripts: Whether the folder contains a ``scripts/`` subdirectory.
        has_references: Whether the folder contains a ``references/`` subdirectory.
        enabled: Whether the automation is currently enabled (from state store).
        last_run: Timestamp of the most recent run, or an empty string.
    """

    name: str
    path: str
    directory: str
    description: str
    activation: ActivationType
    schedule: str = ""
    event: str = ""
    primary_skills: list[str] = []
    secondary_skills: list[str] = []
    has_scripts: bool = False
    has_references: bool = False
    enabled: bool = True
    last_run: str = ""


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
