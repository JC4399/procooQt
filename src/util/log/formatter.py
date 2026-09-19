"""ANSI-colored logging formatter for terminal output."""

from __future__ import annotations

import logging
import sys

_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}

_RESET = "\033[0m"
_GRAY = "\033[90m"
_BOLD = "\033[1m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"
_WHITE_BOLD = "\033[1;37m"
_BLUE = "\033[34m"
_GREEN = "\033[32m"
_BOLD_GREEN = "\033[1;32m"
_BOLD_YELLOW = "\033[1;33m"


class ColoredFormatter(logging.Formatter):
    """Logging formatter that applies ANSI colors based on log level."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        """Initialize the formatter with optional format and date format.

        Args:
            fmt: Optional log message format string.
            datefmt: Optional date format string.
        """
        super().__init__(fmt, datefmt)
        self._use_colors = sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if self._use_colors:
            color = _COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname}{_RESET}"
            record.name = f"{_BOLD}{record.name}{_RESET}"
            record.msg = f"{color}{record.msg}{_RESET}"
            record.asctime = f"{_GRAY}{self.formatTime(record, self.datefmt)}{_RESET}"
            return super().format(record)
        return super().format(record)


def setup_colored_logging(level: int = logging.INFO) -> None:
    """Configure root logger with colored console output.

    Args:
        level: Logging level (default: INFO).
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)


def format_skill_change(skill_name: str, skill_type: str, value: bool) -> str:
    """Return an ANSI-colored string for a skill checkbox change log line."""
    color_val = _WHITE_BOLD + ("True" if value else "False") + _RESET
    return f"Skill  {_MAGENTA}{skill_name:<30}{_RESET} {skill_type}={color_val}"


def format_tool_change(full_tool_name: str, value: str) -> str:
    """Return an ANSI-colored string for a tool radio change log line."""
    color_val = _WHITE_BOLD + value + _RESET
    return f"Tool   {_CYAN}{full_tool_name:<50}{_RESET} mode={color_val}"


def format_preset_save(
    preset_name: str, primary: list[str], secondary: list[str], tools: dict
) -> str:
    """Return an ANSI-colored string for a preset save log line."""
    color_name = _WHITE_BOLD + preset_name + _RESET
    color_label = _GREEN + "save" + _RESET
    return (
        f"Preset {color_label}  {color_name:<30}"
        f"  primary={primary}  secondary={secondary}  tools={tools}"
    )


def format_preset_load(
    preset_name: str, primary: list[str], secondary: list[str], tools: dict
) -> str:
    """Return an ANSI-colored string for a preset load log line."""
    color_name = _WHITE_BOLD + preset_name + _RESET
    color_label = _BLUE + "load" + _RESET
    return (
        f"Preset {color_label}  {color_name:<30}"
        f"  primary={primary}  secondary={secondary}  tools={tools}"
    )


def format_preset_delete(preset_name: str) -> str:
    """Return an ANSI-colored string for a preset delete log line."""
    color_name = _WHITE_BOLD + preset_name + _RESET
    color_label = _COLORS["ERROR"] + "delete" + _RESET
    return f"Preset {color_label}  {color_name}"


def log_session_skills(
    primary_skills: list[str],
    secondary_skills: list[str],
    tool_defs: list[dict],
) -> None:
    """Print loaded session skills and their tools to stderr.

    Args:
        primary_skills: Names of primary (fully loaded) skill paths.
        secondary_skills: Names of secondary (description-only) skill paths.
        tool_defs: Tool definition dicts, each with ``name`` and ``skill_path`` keys.
    """
    primary = ", ".join(primary_skills) if primary_skills else "(none)"
    secondary = ", ".join(secondary_skills) if secondary_skills else "(none)"

    tools_by_skill: dict[str, list[str]] = {}
    for td in tool_defs:
        skill_path = td.get("skill_path", "")
        tools_by_skill.setdefault(skill_path, []).append(td["name"])

    print(f"\n  {_BOLD}session skills{_RESET}", file=sys.stderr)
    print(f"  {_BOLD}primary{_RESET}    {_BOLD_GREEN}{primary}{_RESET}", file=sys.stderr)
    print(f"  {_BOLD}secondary{_RESET}  {_BOLD_YELLOW}{secondary}{_RESET}", file=sys.stderr)
    print(f"  {_BOLD}tools{_RESET}", file=sys.stderr)
    if not primary_skills or not tools_by_skill:
        print(f"      {_GRAY}(none){_RESET}", file=sys.stderr)
    else:
        for skill_path in primary_skills:
            tool_names = tools_by_skill.get(skill_path, [])
            names = ", ".join(tool_names) if tool_names else "(none)"
            print(f"      {_CYAN}{skill_path}{_RESET}: {names}", file=sys.stderr)
    print(file=sys.stderr)
