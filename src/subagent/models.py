"""Pydantic data models for sub-agent requests and their execution results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class SubAgentStatus(StrEnum):
    """Lifecycle state of a spawned sub-agent."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        """Return whether no further state change is possible."""
        return self in (
            SubAgentStatus.DONE,
            SubAgentStatus.ERROR,
            SubAgentStatus.CANCELLED,
        )


class SubAgentSpec(BaseModel):
    """Request describing one headless sub-agent.

    Attributes:
        prompt: The user message the sub-agent runs.
        name: Optional display label used in logs and records.
        model: Model name; empty means the configured sub-agent default.
        primary_skills: Skill paths whose instructions and tools are loaded.
        secondary_skills: Skill paths contributed as descriptions only.
        tools: Explicit tool names; empty means tools from primary skills.
        tool_modes: Per-tool permission overrides (``allow`` or ``block``).
        system_prompt: Optional extra text appended to the base system prompt.
        timeout: Run timeout in seconds; ``0`` means the configured default.
        parent_id: Reserved for nesting; must be empty because nesting is
            disabled.
    """

    prompt: str
    name: str = ""
    model: str = ""
    primary_skills: list[str] = []
    secondary_skills: list[str] = []
    tools: list[str] = []
    tool_modes: dict[str, str] = {}
    system_prompt: str = ""
    timeout: int = 0
    parent_id: str = ""


class SubAgentRecord(BaseModel):
    """Live state and result of one spawned sub-agent.

    Attributes:
        id: Unique sub-agent id (also used as the temporary chat id).
        status: Current lifecycle state.
        spec: The validated request that created the sub-agent.
        model_name: Resolved model name actually used.
        tool_config: Resolved per-tool permission mapping.
        created_at: Creation timestamp as ``"%Y-%m-%d %H:%M:%S"``.
        finished_at: Terminal timestamp, or an empty string while running.
        text: Final assistant text.
        error: Error brief when the run failed.
        tool_calls: Tool-call summaries observed during the run.
        tokens: ``{"input": int, "output": int}`` usage counters.
    """

    id: str
    status: SubAgentStatus
    spec: SubAgentSpec
    model_name: str = ""
    tool_config: dict[str, str] = {}
    created_at: str = ""
    finished_at: str = ""
    text: str = ""
    error: str = ""
    tool_calls: list[dict] = []
    tokens: dict = {}
