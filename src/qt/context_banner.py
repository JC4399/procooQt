"""Context banner items and section formatters.

Builders produce the context banner card and the section builders used by the chat
and skill panels. Banners are derived UI items only: ``session.messages`` remains
canonical. Builders return plain role-keyed dicts consumed by ``ChatListModel``; they
never touch QML objects.
"""

from __future__ import annotations

import json

from .chat_items import KIND_CONTEXT_BANNER, make_item

# ------------------------------------------------------------------
#  Section helpers
# ------------------------------------------------------------------


def _shorten(text: str, limit: int) -> str:
    """Truncate text to *limit* characters, appending an ellipsis.

    Args:
        text: The source text.
        limit: Maximum length before truncation.

    Returns:
        The original text, or a truncated copy ending in ``"..."``.
    """
    return text if len(text) <= limit else text[:limit] + "..."


def _normalize_sections(sections: list[dict]) -> list[dict]:
    """Normalise section content into a JSON-serializable list of strings.

    Content entries that are lists of lines are joined with newlines so QML only
    has to render a flat list of paragraphs per section.

    Args:
        sections: Raw section dicts with ``header`` and ``content`` keys.

    Returns:
        Normalised section dicts with ``header`` (str) and ``content`` (list[str]).
    """
    normalized: list[dict] = []
    for section in sections:
        content: list[str] = []
        for part in section.get("content", []):
            if isinstance(part, str):
                content.append(part)
            elif isinstance(part, list):
                content.append("\n".join(str(line) for line in part))
        normalized.append({"header": section.get("header", ""), "content": content})
    return normalized


# ------------------------------------------------------------------
#  Banner builder
# ------------------------------------------------------------------


def build_context_banner_item(
    title: str,
    sections: list[dict],
    *,
    is_delta: bool = False,
) -> dict[int, object]:
    """Build a context banner card item.

    Args:
        title: The banner headline (e.g. ``"Original System Context"``).
        sections: Section dicts with ``header`` and ``content`` keys; content is
            a list of strings or a list of lists of lines.
        is_delta: Whether to use the delta (orange) colour scheme.

    Returns:
        A role-keyed chat item dictionary with kind ``"context_banner"``. The
        initial (non-delta) banner starts collapsed; delta banners start
        expanded so config changes remain visible.
    """
    normalized = _normalize_sections(sections)
    return make_item(
        KIND_CONTEXT_BANNER,
        title=title,
        sections=json.dumps(normalized),
        collapsed=not is_delta,
        is_delta=is_delta,
    )


# ------------------------------------------------------------------
#  Initial context sections
# ------------------------------------------------------------------


def build_context_sections_from_snapshot(snapshot: dict) -> list[dict]:
    """Convert a context snapshot dict into displayable section dicts.

    Only the full system prompt is emitted; no other snapshot fields follow.

    Args:
        snapshot: A context snapshot dict as stored in session data.

    Returns:
        List of section dicts with ``header`` and ``content`` keys.
    """
    sections: list[dict] = []

    sys_prompt = snapshot.get("system_prompt", "")
    if sys_prompt:
        sections.append({"header": "System Prompt", "content": [f"```\n{sys_prompt}\n```"]})

    return sections


# ------------------------------------------------------------------
#  Delta context sections
# ------------------------------------------------------------------


def build_delta_context_sections(
    added_primary: list[dict],
    added_secondary: list[dict],
    added_tools: list[dict],
    mode_changes: dict[str, tuple[str, str]],
) -> list[dict]:
    """Build section dicts showing what changed in a config delta.

    Args:
        added_primary: Newly added primary skill content dicts.
        added_secondary: Newly added secondary skill content dicts.
        added_tools: Newly added tool definition dicts.
        mode_changes: Mapping of tool name to ``(old_mode, new_mode)``.

    Returns:
        List of section dicts with ``header`` and ``content`` keys.
    """
    sections: list[dict] = []

    if added_primary:
        lines = []
        for skill in added_primary:
            name = skill.get("name", "")
            instructions = _shorten(skill.get("instructions", ""), 200)
            lines.append(f"- **{name}** (primary):\n  {instructions}")
        sections.append({"header": "Added Primary Skills", "content": ["\n".join(lines)]})

    if added_secondary:
        lines = []
        for skill in added_secondary:
            name = skill.get("name", "")
            desc = skill.get("description", "")
            lines.append(f"- **{name}** (secondary):\n  {desc}")
        sections.append({"header": "Added Secondary Skills", "content": ["\n".join(lines)]})

    if added_tools:
        lines = []
        for tool_def in added_tools:
            name = tool_def.get("name", "")
            desc = _shorten(tool_def.get("description", ""), 100)
            lines.append(f"- `{name}` — {desc}")
        sections.append({"header": "Added Tools", "content": ["\n".join(lines)]})

    if mode_changes:
        lines = [
            f"- `{tool_name}`: {old} → {new}"
            for tool_name, (old, new) in sorted(mode_changes.items())
        ]
        sections.append({"header": "Tool Mode Changes", "content": ["\n".join(lines)]})

    return sections
