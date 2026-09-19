"""Pydantic data models for skills, tools, and validation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ValidationLevel(StrEnum):
    """Severity level for a validation issue."""

    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """A single issue found during validation of a skill or tool.

    Attributes:
        level: Severity (``error`` or ``warning``).
        source: Identifier, e.g. ``"skill:Weather Lookup"``
            or ``"tool:execute_python_code (basic)"``.
        message: Human-readable description of the issue.
        field: Name of the problematic field, or empty string.
    """

    level: ValidationLevel
    source: str
    message: str
    field: str = ""


class SkillInfo(BaseModel):
    """Summary metadata for a discovered skill.

    Attributes:
        name: Human-readable skill name (from SKILL.md frontmatter or directory name).
        path: Relative path from skills_dir (e.g. ``"coding/python"``).
        description: Short description of what the skill provides.
        has_tools: Whether the skill directory contains a ``scripts/`` subdirectory.
    """

    name: str
    path: str
    description: str
    has_tools: bool = False


class SkillContent(BaseModel):
    """Full content of a loaded skill, including instructions and bundled assets.

    Attributes:
        name: Skill display name.
        path: Relative path from skills_dir (e.g. ``"coding/python"``).
        description: Short description.
        instructions: Markdown body of the SKILL.md file (system-prompt content).
        scripts: List of filenames in the ``scripts/`` directory.
    """

    name: str
    path: str
    description: str
    instructions: str
    scripts: list[str]


class ToolInfo(BaseModel):
    """Metadata for a single tool discovered inside a skill's ``scripts/`` directory.

    Attributes:
        name: Tool function name (derived from the Python filename without extension).
        skill_path: Relative path of the parent skill from skills_dir.
        description: First line of the tool function's docstring.
        filepath: Absolute path to the tool's ``.py`` file.
    """

    name: str
    skill_path: str
    description: str
    filepath: str
