"""YAML highlighting for tool-call argument cards.

A full port of the Flet edition's YAML tokenizer that emits inline-styled HTML instead
of ``ft.TextSpan`` objects, so QML ``TextEdit.RichText`` renders the same colours. It
handles comment lines, ``key:`` mapping lines, list items, nested indentation, and
inline string/number/boolean detection.
"""

from __future__ import annotations

import html
import re

from .theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CYAN,
    COLOR_ACCENT_GREEN,
    COLOR_ACCENT_MAGENTA,
    COLOR_TEXT_SECONDARY,
)

# ------------------------------------------------------------------
#  Compiled regex
# ------------------------------------------------------------------

_YAML_LIST_KEY_VALUE = re.compile(r"^(\s*)(-\s)?([\w.-]+)(\s*:\s*)(.*)$")
_YAML_LIST_VALUE = re.compile(r"^(\s*)(-\s)(.*)$")
_YAML_KEY_VALUE = re.compile(r"^(\s*)([\w.-]+)(\s*:\s*)(.*)$")

_STRING_DQ = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
_STRING_SQ = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'")
_NUMBER = re.compile(r"\b(\d+\.?\d*)\b")
_BOOLEAN = re.compile(r"\b(true|false|yes|no|null|~)\b", re.IGNORECASE)


# ------------------------------------------------------------------
#  Span helpers
# ------------------------------------------------------------------


def _styled(text: str, color: str, *, italic: bool = False, bold: bool = False) -> str:
    """Wrap escaped text in an inline-styled span.

    Args:
        text: The raw text to wrap.
        color: The hex color for the text.
        italic: Whether to render the text italic.
        bold: Whether to render the text semi-bold (``600``).

    Returns:
        An HTML span element.
    """
    style = f"color:{color}"
    if italic:
        style += ";font-style:italic"
    if bold:
        style += ";font-weight:600"
    return f'<span style="{style}">{html.escape(text)}</span>'


def _plain(text: str) -> str:
    """Escape text that inherits the surrounding colour.

    Args:
        text: The raw text to escape.

    Returns:
        HTML-escaped text with no span wrapper.
    """
    return html.escape(text)


# ------------------------------------------------------------------
#  YAML line tokenizer
# ------------------------------------------------------------------


def _tokenize_line(line: str) -> str:
    """Tokenize a single YAML line (without a trailing newline).

    Args:
        line: A single line of YAML text (no newline).

    Returns:
        Highlighted HTML for the line, or an empty string for empty lines.
    """
    if not line:
        return ""

    if line.lstrip().startswith("#"):
        return _styled(line, COLOR_TEXT_SECONDARY, italic=True)

    match = _YAML_LIST_KEY_VALUE.match(line)
    if match:
        indent, dash, key, colon, value = match.groups()
        return _build_line_html(indent or "", dash or "", key, colon, value)

    match = _YAML_LIST_VALUE.match(line)
    if match:
        indent, dash, value = match.groups()
        return _build_simple_html(indent or "", dash, value)

    match = _YAML_KEY_VALUE.match(line)
    if match:
        indent, key, colon, value = match.groups()
        return _build_line_html(indent or "", "", key, colon, value)

    return _plain(line)


def _build_line_html(indent: str, dash: str, key: str, colon: str, value: str) -> str:
    """Build HTML for a YAML key-value line (possibly with a list dash).

    Args:
        indent: Leading whitespace.
        dash: List dash ``"- "`` or empty.
        key: Key name before the colon.
        colon: Colon with surrounding whitespace.
        value: Value text after the colon.

    Returns:
        Highlighted HTML for the line.
    """
    parts = [_plain(indent)]
    if dash:
        parts.append(_styled(dash, COLOR_ACCENT_BLUE))
    parts.append(_styled(key, COLOR_ACCENT_MAGENTA))
    parts.append(_styled(colon, COLOR_ACCENT_BLUE))
    if value:
        parts.append(_highlight_value(value))
    return "".join(parts)


def _build_simple_html(indent: str, dash: str, value: str) -> str:
    """Build HTML for a simple YAML list line (no key).

    Args:
        indent: Leading whitespace.
        dash: List dash ``"- "``.
        value: Value text.

    Returns:
        Highlighted HTML for the line.
    """
    parts = [_plain(indent), _styled(dash, COLOR_ACCENT_BLUE)]
    if value:
        parts.append(_highlight_value(value))
    return "".join(parts)


def _highlight_value(value: str) -> str:
    """Highlight a YAML value string, detecting strings, numbers, and booleans.

    Args:
        value: A YAML value string.

    Returns:
        Highlighted HTML for the value.
    """
    parts: list[str] = []
    pos = 0
    patterns = (_STRING_DQ, _STRING_SQ, _BOOLEAN, _NUMBER)

    for match in sorted(
        [m for pattern in patterns for m in pattern.finditer(value)],
        key=lambda m: (m.start(), -m.end()),
    ):
        start, end = match.start(), match.end()
        if end <= pos:
            continue
        if start > pos:
            parts.append(_plain(value[pos:start]))
        if match.re is _STRING_DQ or match.re is _STRING_SQ:
            parts.append(_styled(match.group(), COLOR_ACCENT_GREEN))
        elif match.re is _BOOLEAN:
            parts.append(_styled(match.group(), COLOR_ACCENT_CYAN, bold=True))
        elif match.re is _NUMBER:
            parts.append(_styled(match.group(), COLOR_ACCENT_CYAN))
        else:
            parts.append(_plain(match.group()))
        pos = end

    if pos < len(value):
        parts.append(_plain(value[pos:]))

    return "".join(parts)


# ------------------------------------------------------------------
#  Public API
# ------------------------------------------------------------------


def highlight_yaml_html(text: str) -> str:
    """Render YAML as inline-styled HTML for QML rich text.

    Args:
        text: The YAML source.

    Returns:
        An HTML ``<pre>`` block with inline styles.
    """
    lines = [_tokenize_line(line) for line in text.splitlines()]
    body = "\n".join(lines)
    return f'<pre style="white-space:pre-wrap;margin:0">{body}</pre>'
