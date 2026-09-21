"""Chat card item builders.

Card builders return plain role-keyed dictionaries consumed by ``ChatListModel`` and
rendered by QML ``src/qml/cards/*.qml`` delegates. They must not touch QML objects. The
shared :func:`_card_item` helper is the single place that knows the chat role layout,
the token-text format, and the collapsed/pending defaults; every card builder funnels
through it.

Body HTML is pre-rendered here:

* user / tool result — escaped text inside a ``<pre>`` block;
* thinking / response — :func:`render_markdown`;
* tool call — :func:`highlight_yaml_html` over the YAML serializer.
"""

from __future__ import annotations

import contextlib
import html
import json

from .markdown import render_markdown
from .qt_roles import ChatRole
from .theme import FONT_MONO, LINE_HEIGHT_BODY
from .yaml_highlight import highlight_yaml_html

# ------------------------------------------------------------------
#  Item kinds
# ------------------------------------------------------------------
KIND_USER = "user"
KIND_THINKING = "thinking"
KIND_RESPONSE = "response"
KIND_TOOL_CALL = "tool_call"
KIND_TOOL_RESULT = "tool_result"
KIND_CONTEXT_BANNER = "context_banner"
KIND_WAITING = "waiting"


def make_item(
    kind: str,
    *,
    title: str = "",
    body_html: str = "",
    token_text: str = "",
    collapsed: bool = False,
    is_pending: bool = False,
    mode: str = "",
    tool_name: str = "",
    tool_call_id: str = "",
    sections: str = "",
    is_delta: bool = False,
) -> dict[int, object]:
    """Build a chat item keyed by :class:`ChatRole`.

    Args:
        kind: One of the ``KIND_*`` constants.
        title: The card header title.
        body_html: Pre-rendered rich-text HTML body.
        token_text: Formatted token count (e.g. ``"123 tk"``).
        collapsed: Whether the card body starts collapsed.
        is_pending: Whether the card is a pending (streaming) placeholder.
        mode: Tool permission mode for tool-call cards.
        tool_name: Tool name for tool-call/result cards.
        tool_call_id: Tool-call id for result cards.
        sections: JSON-encoded section list for context banners.
        is_delta: Whether a context banner uses the delta colour scheme.

    Returns:
        A role-keyed chat item dictionary.
    """
    return {
        int(ChatRole.KIND): kind,
        int(ChatRole.TITLE): title,
        int(ChatRole.BODY_HTML): body_html,
        int(ChatRole.TOKEN_TEXT): token_text,
        int(ChatRole.COLLAPSED): collapsed,
        int(ChatRole.IS_PENDING): is_pending,
        int(ChatRole.MODE): mode,
        int(ChatRole.TOOL_NAME): tool_name,
        int(ChatRole.TOOL_CALL_ID): tool_call_id,
        int(ChatRole.SECTIONS): sections,
        int(ChatRole.IS_DELTA): is_delta,
    }


# ------------------------------------------------------------------
#  Shared base helper — every builder funnels through this
# ------------------------------------------------------------------


def _token_text(token_count: int) -> str:
    """Format a token count for a card header.

    Args:
        token_count: The estimated token count.

    Returns:
        A string such as ``"42 tk"``.
    """
    return f"{token_count} tk"


def _card_item(
    kind: str,
    *,
    title: str,
    body_html: str = "",
    token_count: int = 0,
    is_pending: bool = False,
    mode: str = "",
    tool_name: str = "",
    tool_call_id: str = "",
) -> dict[int, object]:
    """Build one card item with the shared header/token/pending defaults.

    Args:
        kind: One of the ``KIND_*`` constants.
        title: The card header title.
        body_html: Pre-rendered rich-text HTML body.
        token_count: Token count rendered in the header.
        is_pending: Whether the card is a pending (streaming) placeholder.
        mode: Tool permission mode for tool-call cards.
        tool_name: Tool name for tool-call/result cards.
        tool_call_id: Tool-call id for result cards.

    Returns:
        A role-keyed chat item dictionary.
    """
    return make_item(
        kind,
        title=title,
        body_html=body_html,
        token_text=_token_text(token_count),
        is_pending=is_pending,
        mode=mode,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
    )


def _plain_body(text: str) -> str:
    """Wrap escaped plain text in a preformatted block.

    Args:
        text: The raw text to display.

    Returns:
        An HTML ``<pre>`` block preserving whitespace and newlines.
    """
    return (
        f'<pre style="white-space:pre-wrap;margin:0;font-family:{FONT_MONO};'
        f'line-height:{LINE_HEIGHT_BODY}">{html.escape(text)}</pre>'
    )


# ------------------------------------------------------------------
#  User card
# ------------------------------------------------------------------


def build_user_item(text: str) -> dict[int, object]:
    """Build a user message card item.

    Args:
        text: User message text.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(KIND_USER, title="User", body_html=_plain_body(text))


# ------------------------------------------------------------------
#  Waiting placeholder
# ------------------------------------------------------------------


def build_waiting_item() -> dict[int, object]:
    """Build the pending placeholder shown while awaiting the first assistant token.

    Emitted at the end of the render plan while a generation is busy but the
    current assistant turn has produced no thinking, response, or tool-call
    content yet (model prefill, a stalled network, or a pending failure). The
    body is empty, so QML renders the headerless scanner; the first real card
    replaces this row through ``diff_update``.

    Returns:
        A role-keyed chat item dictionary.
    """
    return make_item(KIND_WAITING, is_pending=True)


# ------------------------------------------------------------------
#  Thinking card
# ------------------------------------------------------------------


def build_thinking_item(text: str, *, token_count: int = 0) -> dict[int, object]:
    """Build a completed thinking card item.

    Args:
        text: Thinking content.
        token_count: Token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(
        KIND_THINKING,
        title="Thinking",
        body_html=render_markdown(text),
        token_count=token_count,
    )


def build_thinking_pending_item(text: str = "", *, token_count: int = 0) -> dict[int, object]:
    """Build a pending (streaming) thinking card item.

    The body is rendered from the partial text so the card streams live; it stays
    ``is_pending`` until the message finalises. An empty ``text`` yields a
    body-less card that QML shows as a spinner.

    Args:
        text: Partial thinking content to render as the streaming body.
        token_count: Initial token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(
        KIND_THINKING,
        title="Thinking",
        body_html=render_markdown(text),
        token_count=token_count,
        is_pending=True,
    )


# ------------------------------------------------------------------
#  Response card
# ------------------------------------------------------------------


def build_response_item(text: str, *, token_count: int = 0) -> dict[int, object]:
    """Build a completed assistant response card item.

    Args:
        text: Response content in markdown.
        token_count: Token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(
        KIND_RESPONSE,
        title="Response",
        body_html=render_markdown(text),
        token_count=token_count,
    )


def build_response_pending_item(text: str = "", *, token_count: int = 0) -> dict[int, object]:
    """Build a pending (streaming) assistant response card item.

    The body is rendered from the partial text so the card streams live; it stays
    ``is_pending`` until the message finalises. An empty ``text`` yields a
    body-less card that QML shows as a spinner.

    Args:
        text: Partial response content to render as the streaming body.
        token_count: Initial token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(
        KIND_RESPONSE,
        title="Response",
        body_html=render_markdown(text),
        token_count=token_count,
        is_pending=True,
    )


# ------------------------------------------------------------------
#  Tool argument parsing and YAML formatting
# ------------------------------------------------------------------


def _parse_tool_arguments(tc: dict) -> dict | list:
    """Parse tool arguments from an OpenAI-format tool_call entry.

    Args:
        tc: A tool_call dict with ``function.arguments`` as a JSON string,
            or a raw dict/list during streaming.

    Returns:
        Parsed dict or list, or an empty dict on parse failure.
    """
    args_raw = tc.get("function", {}).get("arguments", "{}")
    if isinstance(args_raw, (dict, list)):
        return args_raw
    try:
        result = json.loads(args_raw)
        if isinstance(result, (dict, list)):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _yaml_quote(value: str) -> str:
    """Return a YAML double-quoted string with proper escaping.

    Args:
        value: The raw string value.

    Returns:
        A double-quoted, escaped YAML scalar.
    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _format_yaml_value(value: object, indent: int) -> list[str]:
    """Format a single YAML value into indented lines.

    Args:
        value: The Python value (dict, list, str, int, float, bool, None).
        indent: Current indentation level (number of spaces).

    Returns:
        List of YAML text lines for this value.
    """
    prefix = " " * indent

    if isinstance(value, dict):
        lines: list[str] = []
        for k, v in value.items():
            if isinstance(v, str) and "\n" in v:
                lines.append(f"{prefix}{k}: |")
                for sub in v.split("\n"):
                    lines.append(f"{prefix}  {sub}")
            elif isinstance(v, (dict, list)):
                lines.append(f"{prefix}{k}:")
                lines.extend(_format_yaml_value(v, indent + 2))
            elif isinstance(v, bool):
                lines.append(f"{prefix}{k}: {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{prefix}{k}: {v}")
            elif v is None:
                lines.append(f"{prefix}{k}: null")
            else:
                lines.append(f"{prefix}{k}: {_yaml_quote(str(v))}")
        return lines

    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_format_yaml_value(item, indent + 2))
            elif isinstance(item, str) and "\n" in item:
                lines.append(f"{prefix}- |")
                for sub in item.split("\n"):
                    lines.append(f"{prefix}  {sub}")
            elif isinstance(item, bool):
                lines.append(f"{prefix}- {'true' if item else 'false'}")
            elif isinstance(item, (int, float)):
                lines.append(f"{prefix}- {item}")
            elif item is None:
                lines.append(f"{prefix}- null")
            else:
                lines.append(f"{prefix}- {_yaml_quote(str(item))}")
        return lines

    if isinstance(value, str) and "\n" in value:
        lines = [f"{prefix}|"]
        lines.extend(f"{prefix}{sub}" for sub in value.split("\n"))
        return lines

    if isinstance(value, str):
        return [f"{prefix}{_yaml_quote(value)}"]

    if isinstance(value, bool):
        return [f"{prefix}{'true' if value else 'false'}"]

    if isinstance(value, (int, float)):
        return [f"{prefix}{value}"]

    if value is None:
        return [f"{prefix}null"]

    return [f"{prefix}{value}"]


def _to_yaml_string(entry: dict) -> str:
    """Convert a tool call entry dict to a YAML-formatted string.

    Args:
        entry: Tool call entry with ``name``, ``mode``, ``arguments`` keys.

    Returns:
        YAML string. Multiline argument values use a literal block scalar.
    """
    args = entry.get("arguments", {})
    if isinstance(args, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            args = json.loads(args)

    lines: list[str] = [f"name: {entry.get('name', '')}"]
    lines.append(f"mode: {entry.get('mode', 'ask')}")
    lines.append("arguments:")
    lines.extend(_format_yaml_value(args, 2))
    return "\n".join(lines)


# ------------------------------------------------------------------
#  Tool call card
# ------------------------------------------------------------------


def build_tool_call_item(entry: dict, *, token_count: int = 0) -> dict[int, object]:
    """Build a finalized tool call card item.

    Args:
        entry: Tool call entry with ``name``, ``mode``, ``arguments`` keys.
        token_count: Token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    name = entry.get("name", "")
    mode = entry.get("mode", "ask")
    yaml_str = _to_yaml_string(
        {"name": name, "mode": mode, "arguments": entry.get("arguments", {})}
    )
    return _card_item(
        KIND_TOOL_CALL,
        title="Tool Call",
        body_html=highlight_yaml_html(yaml_str.strip()),
        token_count=token_count,
        mode=mode,
        tool_name=name,
    )


def build_tool_call_pending_item(name: str, mode: str, token_count: int = 0) -> dict[int, object]:
    """Build a pending tool call card item.

    Args:
        name: Tool name.
        mode: Tool permission mode (``"allow"``, ``"ask"``, ``"block"``).
        token_count: Initial argument token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(
        KIND_TOOL_CALL,
        title="Tool Call",
        token_count=token_count,
        is_pending=True,
        mode=mode,
        tool_name=name,
    )


# ------------------------------------------------------------------
#  Tool result card
# ------------------------------------------------------------------


def build_tool_result_item(name: str, content: str, *, token_count: int = 0) -> dict[int, object]:
    """Build a completed tool result card item.

    Args:
        name: Tool name.
        content: Result content text.
        token_count: Token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(
        KIND_TOOL_RESULT,
        title="Tool Result",
        body_html=_plain_body(content),
        token_count=token_count,
        tool_name=name,
    )


def build_tool_result_pending_item(
    name: str, tool_call_id: str = "", token_count: int = 0
) -> dict[int, object]:
    """Build a pending tool result card item.

    Args:
        name: Tool name displayed in the header.
        tool_call_id: The tool-call id used to match the eventual result.
        token_count: Initial token count displayed in the header.

    Returns:
        A role-keyed chat item dictionary.
    """
    return _card_item(
        KIND_TOOL_RESULT,
        title="Tool Result",
        token_count=token_count,
        is_pending=True,
        tool_name=name,
        tool_call_id=tool_call_id,
    )
