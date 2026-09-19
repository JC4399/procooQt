"""Custom exception hierarchy for the Procoo Qt application.

Each exception carries a *brief* message (for the Qt UI toast) and a
*detail* message (for the terminal log).  If only one is supplied the other
defaults to it, so raising ``ConfigError("Missing key")`` works without
explicitly setting both.
"""

from __future__ import annotations


class ProcooError(Exception):
    """Base application error with separate brief (UI) and detail (terminal) messages.

    Attributes:
        brief: Short message shown in the Qt error toast.
        detail: Full message (with context / traceback) logged to terminal.
        category: Domain tag — ``"config"``, ``"agent"``, ``"tool"``, or ``"session"``.
    """

    category: str = "general"

    def __init__(
        self,
        brief: str = "",
        detail: str | None = None,
        *,
        category: str | None = None,
    ) -> None:
        self.brief = brief
        self.detail = detail if detail is not None else brief
        if category is not None:
            self.category = category
        super().__init__(self.detail)


class ConfigError(ProcooError):
    """Raised when a required configuration key is missing or invalid."""

    category = "config"


class AgentError(ProcooError):
    """Raised when the LLM agent fails during generation."""

    category = "agent"


class ToolError(ProcooError):
    """Raised when a tool cannot be loaded or executed."""

    category = "tool"


class SessionError(ProcooError):
    """Raised when a session operation fails."""

    category = "session"
