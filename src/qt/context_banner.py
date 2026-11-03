"""Context banner items and section formatters.

Builders produce the context banner card and the section builders used by the chat
and skill panels. Banners are derived UI items only: ``chat.messages`` remains
canonical. Builders return plain role-keyed dicts consumed by ``ChatListModel``; they
never touch QML objects.
"""

from __future__ import annotations

import json

from .chat_items import KIND_CONTEXT_BANNER, make_item

# ------------------------------------------------------------------
#  Section helpers
# ------------------------------------------------------------------


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


def build_system_prompt_section(text: str) -> list[dict]:
    """Build the fenced ``System Prompt`` section used by every context banner.

    Both the initial system-context card and the skill-update card use this
    helper, so their bodies render identically: the exact system-message text in
    a fenced block.

    Args:
        text: The exact system-message text.

    Returns:
        A single-section list with the fenced text, or an empty list when the
        text is empty.
    """
    if not text:
        return []
    return [{"header": "System Prompt", "content": [f"```\n{text}\n```"]}]


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
        snapshot: A context snapshot dict as stored in chat data.

    Returns:
        List of section dicts with ``header`` and ``content`` keys.
    """
    return build_system_prompt_section(snapshot.get("system_prompt", ""))


# ------------------------------------------------------------------
#  Skill update sections
# ------------------------------------------------------------------


def build_skill_update_sections(pending_text: str) -> list[dict]:
    """Build the section list for a skill-update context card.

    The card body is the exact system-message text that will be injected before
    the next user message, formatted identically to the initial prompt card.

    Args:
        pending_text: The exact pending system-message text.

    Returns:
        List of section dicts with ``header`` and ``content`` keys.
    """
    return build_system_prompt_section(pending_text)
