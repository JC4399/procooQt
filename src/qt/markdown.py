"""Markdown rendering for chat cards.

Renders CommonMark (plus tables, strikethrough, task lists, and footnotes) to
inline-styled HTML for QML ``TextEdit.RichText`` using ``markdown-it-py``, with fenced
code blocks highlighted by ``pygments`` (``noclasses=True``). The output is sanitized:
``<script>``/``<style>`` blocks, ``on*`` event attributes, and ``javascript:`` URLs are
dropped because the source is untrusted LLM output.
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

# ------------------------------------------------------------------
#  Code highlighting
# ------------------------------------------------------------------

_FORMATTER = HtmlFormatter(nowrap=True, noclasses=True, style="monokai")


def _highlight_code(code: str, lang: str, _attrs: str) -> str:
    """Highlight a fenced code block.

    Args:
        code: The raw code text.
        lang: The language hint from the fence, or an empty string.
        _attrs: Extra fence attributes (unused).

    Returns:
        Inline-styled HTML, or an empty string to fall back to plain escaping.
    """
    lexer = None
    if lang:
        try:
            lexer = get_lexer_by_name(lang)
        except ClassNotFound:
            lexer = None
    if lexer is None:
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            return ""
    return str(highlight(code, lexer, _FORMATTER))


# ------------------------------------------------------------------
#  Sanitizer
# ------------------------------------------------------------------

_SCRIPT_STYLE_RE = re.compile(
    r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL
)
_EVENT_ATTR_RE = re.compile(r"\son\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URL_RE = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", re.IGNORECASE)


def _sanitize(fragment: str) -> str:
    """Strip scripts, event handlers, and javascript: URLs from rendered HTML.

    Args:
        fragment: The rendered HTML fragment.

    Returns:
        The sanitized fragment.
    """
    fragment = _SCRIPT_STYLE_RE.sub("", fragment)
    fragment = _EVENT_ATTR_RE.sub("", fragment)
    return _JS_URL_RE.sub("", fragment)


# ------------------------------------------------------------------
#  Renderer
# ------------------------------------------------------------------

_MD = MarkdownIt("commonmark", {"highlight": _highlight_code})
_MD.enable(["table", "strikethrough"])
_MD.use(tasklists_plugin, enabled=True)
_MD.use(footnote_plugin)


def render_markdown(text: str) -> str:
    """Render markdown to inline-styled HTML for QML rich text.

    Args:
        text: The markdown source.

    Returns:
        An HTML fragment with inline styles (no CSS classes, no scripts).
    """
    if not text:
        return ""
    return _sanitize(_MD.render(text))
