"""Terminal-style Markdown rendering for chat cards.

Renders CommonMark (plus tables, strikethrough, task lists, footnotes, and
dollar-delimited LaTeX math) to inline-styled HTML for QML ``TextEdit.RichText``.
The output mimics a TUI markdown pager: syntax marks are concealed, each element
gets an explicit color, block quotes get a drawn left border, lists use literal
monospace markers, and tables are rendered as CSS tables with collapsed borders.
Fenced code blocks are highlighted by ``pygments`` using
:class:`_MarkdownCodeStyle`. Math spans are rasterised in memory by
:func:`~src.qt.latex.render_math_fragment` and inlined as ``data:`` URI images,
so no temporary files are created.

Because the source is untrusted LLM output, the fragment is sanitized:
``<script>``/``<style>`` blocks, ``on*`` event attributes, and unsafe URL schemes are
dropped.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
import threading

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.style import Style
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Text
from pygments.util import ClassNotFound

from .latex import render_math_fragment
from .theme import (
    COLOR_MD_BOLD,
    COLOR_MD_CODE,
    COLOR_MD_HEADING,
    COLOR_MD_ITALIC,
    COLOR_MD_LINK,
    COLOR_MD_LIST_MARKER,
    COLOR_MD_LIST_NUMBER,
    COLOR_MD_QUOTE,
    COLOR_MD_RULE,
    COLOR_MD_TEXT,
    FONT_MONO,
    FONT_SIZE_MARKDOWN,
    LINE_HEIGHT_BODY,
)

# ------------------------------------------------------------------
#  Code highlighting
# ------------------------------------------------------------------


class _MarkdownCodeStyle(Style):
    """Pygments style matching the terminal markdown palette."""

    name = "procoo-markdown"
    background_color = "#000000"
    styles = {  # noqa: RUF012 - mirrors pygments' unannotated class attribute
        Text: COLOR_MD_TEXT,
        Comment: f"italic {COLOR_MD_QUOTE}",
        Keyword: COLOR_MD_HEADING,
        Keyword.Type: COLOR_MD_ITALIC,
        Keyword.Namespace: COLOR_MD_BOLD,
        Name: COLOR_MD_TEXT,
        Name.Builtin: COLOR_MD_LINK,
        Name.Function: COLOR_MD_LINK,
        Name.Class: COLOR_MD_ITALIC,
        Name.Decorator: COLOR_MD_BOLD,
        Number: COLOR_MD_ITALIC,
        String: COLOR_MD_CODE,
        Operator: COLOR_MD_LINK,
        Punctuation: COLOR_MD_TEXT,
    }


#: One formatter per thread. Pygments formatters are not guaranteed
#: thread-safe, and each chat renders on its own worker thread, so the
#: formatter must not be shared across threads.
_FORMATTER_TLS = threading.local()


def _formatter() -> HtmlFormatter:
    """Return this thread's pygments formatter, creating it on first use.

    Returns:
        A thread-local ``HtmlFormatter``.
    """
    formatter: HtmlFormatter | None = getattr(_FORMATTER_TLS, "formatter", None)
    if formatter is None:
        formatter = HtmlFormatter(nowrap=True, noclasses=True, style=_MarkdownCodeStyle)
        _FORMATTER_TLS.formatter = formatter
    return formatter


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
    return str(highlight(code, lexer, _formatter()))


# ------------------------------------------------------------------
#  Sanitizer
# ------------------------------------------------------------------

_SCRIPT_STYLE_RE = re.compile(
    r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL
)
_EVENT_ATTR_RE = re.compile(r"\son\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URL_RE = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", re.IGNORECASE)
_UNSAFE_URL_RE = re.compile(r"^\s*(?:javascript|data|vbscript):", re.IGNORECASE)


def _sanitize(fragment: str) -> str:
    """Strip scripts, event handlers, and unsafe URLs from rendered HTML.

    Args:
        fragment: The rendered HTML fragment.

    Returns:
        The sanitized fragment.
    """
    fragment = _SCRIPT_STYLE_RE.sub("", fragment)
    fragment = _EVENT_ATTR_RE.sub("", fragment)
    return _JS_URL_RE.sub("", fragment)


def _safe_href(url: str) -> str:
    """Return a link target, or an empty string for unsafe schemes.

    Args:
        url: The raw URL from a link or image token.

    Returns:
        The URL when safe, otherwise an empty string.
    """
    return "" if _UNSAFE_URL_RE.match(url or "") else (url or "")


# ------------------------------------------------------------------
#  Monospace measurement
# ------------------------------------------------------------------

#: Approximate advance width of one monospace cell in logical pixels, used for
#: list hanging indents. Derived from the markdown font point size assuming a
#: half-em advance at 96 DPI. Qt font metrics cannot be queried here because no
#: ``QGuiApplication`` exists at render time in headless/test contexts.
_CHAR_PX = FONT_SIZE_MARKDOWN * 2 / 3

#: Bottom margin (logical pixels) applied to top-level paragraphs and headings so
#: a blank line in the Markdown source renders as one visible empty line.
_BLANK_LINE_PX = FONT_SIZE_MARKDOWN


# ------------------------------------------------------------------
#  Terminal renderer
# ------------------------------------------------------------------


@dataclass
class _ListCtx:
    """State for one open list level.

    Attributes:
        ordered: Whether the list is ordered.
        index: The next ordered-list number.
    """

    ordered: bool
    index: int


@dataclass
class _ItemCtx:
    """State for one open list item.

    Attributes:
        marker: Colored HTML marker (``-`` or ``1.``).
        margin: Left margin in pixels.
        indent: First-line text indent in pixels (negative for hanging indent).
        pending: Whether the marker block has yet to be emitted.
        marker_para: Whether the paragraph currently closing is the marker block.
    """

    marker: str
    margin: float
    indent: float
    pending: bool = True
    marker_para: bool = False


class _TerminalRenderer(RendererHTML):
    """Render markdown tokens to terminal-style inline-styled HTML."""

    def __init__(self, parser: object = None) -> None:
        """Initialise the renderer and its per-document state.

        Args:
            parser: The owning parser (unused; matches the base signature).
        """
        super().__init__(parser)
        self._reset()

    def _reset(self) -> None:
        """Reset per-document render state."""
        self._lists: list[_ListCtx] = []
        self._items: list[_ItemCtx] = []
        self._links: list[bool] = []

    # ------------------------------------------------------------------
    #  Render loop override
    # ------------------------------------------------------------------

    def render(self, tokens: Sequence[Token], options: OptionsDict, env: EnvType) -> str:
        """Render a token stream, resetting state first.

        Args:
            tokens: Block-level tokens.
            options: Parser options.
            env: Parser environment.

        Returns:
            The rendered HTML fragment.
        """
        self._reset()
        return super().render(tokens, options, env)

    # ------------------------------------------------------------------
    #  Inline tokens
    # ------------------------------------------------------------------

    def text(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Render a text run.

        Args:
            tokens: Inline tokens.
            idx: Index of the text token.
            options: Parser options.
            env: Parser environment.

        Returns:
            Escaped text.
        """
        return escapeHtml(tokens[idx].content)

    def softbreak(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Render a soft line break.

        Returns:
            A newline (collapsed to a space in the paragraph).
        """
        return "\n"

    def hardbreak(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Render a hard line break.

        Returns:
            A ``<br>`` tag.
        """
        return "<br>\n"

    def strong_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a bold run in orange.

        Returns:
            The opening HTML.
        """
        return f'<b><font color="{COLOR_MD_BOLD}">'

    def strong_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a bold run.

        Returns:
            The closing HTML.
        """
        return "</font></b>"

    def em_open(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Open an italic run in yellow.

        Returns:
            The opening HTML.
        """
        return f'<i><font color="{COLOR_MD_ITALIC}">'

    def em_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close an italic run.

        Returns:
            The closing HTML.
        """
        return "</font></i>"

    def s_open(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Open a struck-through run.

        Returns:
            The opening HTML.
        """
        return "<s>"

    def s_close(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Close a struck-through run.

        Returns:
            The closing HTML.
        """
        return "</s>"

    def code_inline(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Render inline code in green.

        Args:
            tokens: Inline tokens.
            idx: Index of the code token.
            options: Parser options.
            env: Parser environment.

        Returns:
            The styled code span.
        """
        return f'<font color="{COLOR_MD_CODE}">{escapeHtml(tokens[idx].content)}</font>'

    def link_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a link label in cyan with an underline.

        Args:
            tokens: Inline tokens.
            idx: Index of the link token.
            options: Parser options.
            env: Parser environment.

        Returns:
            The opening anchor, or an empty string for unsafe URLs.
        """
        href = _safe_href(str(tokens[idx].attrs.get("href", "")))
        self._links.append(bool(href))
        if not href:
            return ""
        return f'<a href="{escapeHtml(href)}"><u><font color="{COLOR_MD_LINK}">'

    def link_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a link opened by :meth:`link_open`.

        Returns:
            The closing HTML, or an empty string when the link was suppressed.
        """
        if not self._links:
            return ""
        return "</font></u></a>" if self._links.pop() else ""

    def image(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Render an image as its alt text used as a link label.

        Args:
            tokens: Inline tokens.
            idx: Index of the image token.
            options: Parser options.
            env: Parser environment.

        Returns:
            A cyan underlined label linking to the image source.
        """
        token = tokens[idx]
        src = _safe_href(str(token.attrs.get("src", "")))
        label = self.renderInlineAsText(token.children, options, env) or src
        if not src:
            return escapeHtml(label)
        label_html = escapeHtml(label)
        return (
            f'<a href="{escapeHtml(src)}">'
            f'<u><font color="{COLOR_MD_LINK}">{label_html}</font></u></a>'
        )

    def math_inline(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Render an inline LaTeX span as an in-memory PNG.

        Args:
            tokens: Inline tokens.
            idx: Index of the math token.
            options: Parser options.
            env: Parser environment.

        Returns:
            An ``<img>`` backed by a ``data:`` URI, falling back to the literal
            ``$…$`` source when the expression cannot be rendered.
        """
        content = tokens[idx].content
        fragment = render_math_fragment(content, display=False)
        return fragment or escapeHtml(f"${content}$")

    def html_inline(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Convert a task-list checkbox to a literal marker, dropping other HTML.

        Args:
            tokens: Inline tokens.
            idx: Index of the raw HTML token.
            options: Parser options.
            env: Parser environment.

        Returns:
            ``[x]`` or ``[ ]`` for checkboxes, otherwise an empty string.
        """
        content = tokens[idx].content
        if "checkbox" not in content:
            return ""
        return "[x]" if "checked" in content else "[ ]"

    def html_block(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Drop raw HTML blocks.

        Returns:
            An empty string.
        """
        return ""

    # ------------------------------------------------------------------
    #  Block tokens
    # ------------------------------------------------------------------

    def heading_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a heading in accent purple; h1 is additionally underlined.

        Args:
            tokens: Block tokens.
            idx: Index of the heading token.
            options: Parser options.
            env: Parser environment.

        Returns:
            The opening paragraph with heading styling.
        """
        underline = "text-decoration:underline;" if tokens[idx].tag == "h1" else ""
        return (
            f'<p style="margin:0 0 {_BLANK_LINE_PX}px 0;color:{COLOR_MD_HEADING};font-weight:bold;'
            f'{underline}line-height:{LINE_HEIGHT_BODY}">'
        )

    def heading_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a heading.

        Returns:
            The closing paragraph tag.
        """
        return "</p>"

    def paragraph_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a paragraph, or the marker block of a list item.

        Args:
            tokens: Block tokens.
            idx: Index of the paragraph token.
            options: Parser options.
            env: Parser environment.

        Returns:
            The opening HTML.
        """
        if self._items and self._items[-1].pending:
            item = self._items[-1]
            item.pending = False
            item.marker_para = True
            return (
                f'<div style="margin-left:{item.margin:.1f}px;'
                f"text-indent:{item.indent:.1f}px;"
                f'line-height:{LINE_HEIGHT_BODY}">{item.marker} '
            )
        if tokens[idx].hidden:
            return ""
        return f'<p style="margin:0 0 {_BLANK_LINE_PX}px 0;line-height:{LINE_HEIGHT_BODY}">'

    def paragraph_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a paragraph, or the marker block of a list item.

        Returns:
            The closing HTML.
        """
        if self._items and self._items[-1].marker_para:
            self._items[-1].marker_para = False
            return "</div>"
        if tokens[idx].hidden:
            return ""
        return "</p>"

    def blockquote_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a block quote as a two-cell table with a colored stripe.

        Qt Quick's ``TextEdit`` does not paint cell ``border-left``, so the
        vertical bar is a narrow background-filled cell.

        Returns:
            The opening table HTML.
        """
        return (
            '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
            f'<td width="2" bgcolor="{COLOR_MD_QUOTE}"></td>'
            f'<td style="padding-left:8px;color:{COLOR_MD_ITALIC};'
            f'font-style:italic;line-height:{LINE_HEIGHT_BODY}">'
        )

    def blockquote_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a block quote table.

        Returns:
            The closing table HTML.
        """
        return "</td></tr></table>"

    def hr(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Render a horizontal rule.

        Returns:
            A grey rule.
        """
        return f'<hr style="border:none;border-top:1px solid {COLOR_MD_RULE}">'

    def fence(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Render a fenced code block with visible, grey fence lines.

        Args:
            tokens: Block tokens.
            idx: Index of the fence token.
            options: Parser options.
            env: Parser environment.

        Returns:
            A highlighted, preformatted block including its fences.
        """
        token = tokens[idx]
        info = (token.info or "").strip()
        lang = info.split(maxsplit=1)[0] if info else ""
        body = _highlight_code(token.content, lang, "") or escapeHtml(token.content)
        body = body.rstrip("\n")
        fence = f'<font color="{COLOR_MD_RULE}">```{escapeHtml(lang)}</font>'
        return (
            f'<pre style="white-space:pre-wrap;margin:0 0 {_BLANK_LINE_PX}px 0;'
            f"font-family:{FONT_MONO};"
            f'line-height:{LINE_HEIGHT_BODY}">'
            f"{fence}\n{body}\n"
            f'<font color="{COLOR_MD_RULE}">```</font></pre>\n'
        )

    def code_block(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Render an indented code block.

        Args:
            tokens: Block tokens.
            idx: Index of the code token.
            options: Parser options.
            env: Parser environment.

        Returns:
            A preformatted block.
        """
        body = escapeHtml(tokens[idx].content).rstrip("\n")
        return (
            f'<pre style="white-space:pre-wrap;margin:0 0 {_BLANK_LINE_PX}px 0;'
            f"font-family:{FONT_MONO};"
            f'line-height:{LINE_HEIGHT_BODY}">{body}</pre>\n'
        )

    def math_block(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Render a display LaTeX equation as a centred in-memory PNG.

        Args:
            tokens: Block tokens.
            idx: Index of the math token.
            options: Parser options.
            env: Parser environment.

        Returns:
            A centred ``<div>`` wrapping the ``<img>``, or an escaped ``<pre>``
            block when the expression cannot be rendered.
        """
        content = tokens[idx].content
        fragment = render_math_fragment(content, display=True)
        if not fragment:
            body = escapeHtml(content).rstrip("\n")
            return (
                f'<pre style="white-space:pre-wrap;margin:0 0 {_BLANK_LINE_PX}px 0;'
                f'font-family:{FONT_MONO};line-height:{LINE_HEIGHT_BODY}">'
                f"{body}</pre>\n"
            )
        return (
            f'<div style="text-align:center;margin:0 0 {_BLANK_LINE_PX}px 0;'
            f'line-height:{LINE_HEIGHT_BODY}">{fragment}</div>\n'
        )

    # ------------------------------------------------------------------
    #  Lists
    # ------------------------------------------------------------------

    def _flush_pending_marker(self) -> str:
        """Emit a marker block for an item that did not start with a paragraph.

        Returns:
            A closed marker ``<div>``, or an empty string.
        """
        if not self._items or not self._items[-1].pending:
            return ""
        item = self._items[-1]
        item.pending = False
        return (
            f'<div style="margin-left:{item.margin:.1f}px;'
            f"text-indent:{item.indent:.1f}px;"
            f'line-height:{LINE_HEIGHT_BODY}">{item.marker} </div>'
        )

    def bullet_list_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open an unordered list.

        Returns:
            A pending marker block if the parent item needs one, else empty.
        """
        prefix = self._flush_pending_marker()
        self._lists.append(_ListCtx(ordered=False, index=1))
        return prefix

    def ordered_list_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open an ordered list.

        Args:
            tokens: Block tokens.
            idx: Index of the list token.
            options: Parser options.
            env: Parser environment.

        Returns:
            A pending marker block if the parent item needs one, else empty.
        """
        prefix = self._flush_pending_marker()
        start = int(tokens[idx].attrs.get("start", 1) or 1)
        self._lists.append(_ListCtx(ordered=True, index=start))
        return prefix

    def bullet_list_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close an unordered list.

        Returns:
            An empty string.
        """
        if self._lists:
            self._lists.pop()
        return ""

    def ordered_list_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close an ordered list.

        Returns:
            An empty string.
        """
        if self._lists:
            self._lists.pop()
        return ""

    def list_item_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a list item and stage its colored marker.

        Args:
            tokens: Block tokens.
            idx: Index of the item token.
            options: Parser options.
            env: Parser environment.

        Returns:
            An empty string; the marker is emitted with the first block.
        """
        if not self._lists:
            return ""
        ctx = self._lists[-1]
        depth = len(self._lists) - 1
        if ctx.ordered:
            marker_plain = f"{ctx.index}."
            color = COLOR_MD_LIST_NUMBER
            ctx.index += 1
        else:
            marker_plain = "-"
            color = COLOR_MD_LIST_MARKER
        char = _CHAR_PX
        marker_cols = len(marker_plain) + 1
        margin = depth * 2 * char + marker_cols * char
        self._items.append(
            _ItemCtx(
                marker=f'<font color="{color}">{marker_plain}</font>',
                margin=margin,
                indent=-marker_cols * char,
            )
        )
        return ""

    def list_item_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a list item, flushing an unused marker if needed.

        Returns:
            A marker block for a paragraph-less item, else an empty string.
        """
        prefix = self._flush_pending_marker()
        if self._items:
            self._items.pop()
        return prefix

    # ------------------------------------------------------------------
    #  Tables
    # ------------------------------------------------------------------

    _CELL_STYLE = f"padding:4px;line-height:{LINE_HEIGHT_BODY}"

    def _cell_open(self, tag: str, tokens: Sequence[Token], idx: int) -> str:
        """Open a table cell with padding and markdown alignment.

        Args:
            tag: ``"th"`` or ``"td"``.
            tokens: Block tokens.
            idx: Index of the cell token.

        Returns:
            The opening cell HTML.
        """
        style = self._CELL_STYLE
        align = tokens[idx].attrs.get("style")
        if align:
            style = f"{style};{align}"
        return f'<{tag} style="{style}">'

    def table_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a CSS table with collapsed borders.

        Qt Quick's ``TextEdit`` ignores CSS ``border`` on cells but honors the
        table ``border`` attribute coloured by CSS ``border-color``.

        Returns:
            The opening ``<table>`` HTML.
        """
        return (
            f'<table border="1" cellspacing="0" cellpadding="0" '
            f'style="border-collapse:collapse;border-color:{COLOR_MD_RULE};'
            f'margin:0 0 {_BLANK_LINE_PX}px 0">'
        )

    def table_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close the CSS table.

        Returns:
            The closing ``</table>`` HTML.
        """
        return "</table>\n"

    def thead_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a table head section.

        Returns:
            An empty string.
        """
        return ""

    def thead_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a table head section.

        Returns:
            An empty string.
        """
        return ""

    def tbody_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Open a table body section.

        Returns:
            An empty string.
        """
        return ""

    def tbody_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a table body section.

        Returns:
            An empty string.
        """
        return ""

    def tr_open(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Open a table row.

        Returns:
            The opening ``<tr>`` HTML.
        """
        return "<tr>"

    def tr_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a table row.

        Returns:
            The closing ``</tr>`` HTML.
        """
        return "</tr>"

    def th_open(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Open a header cell.

        Returns:
            The opening ``<th>`` HTML.
        """
        return self._cell_open("th", tokens, idx)

    def th_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a header cell.

        Returns:
            The closing ``</th>`` HTML.
        """
        return "</th>"

    def td_open(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        """Open a data cell.

        Returns:
            The opening ``<td>`` HTML.
        """
        return self._cell_open("td", tokens, idx)

    def td_close(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        """Close a data cell.

        Returns:
            The closing ``</td>`` HTML.
        """
        return "</td>"


# ------------------------------------------------------------------
#  Renderer
# ------------------------------------------------------------------


def _build_parser() -> MarkdownIt:
    """Create a configured ``MarkdownIt`` parser.

    Returns:
        A parser with terminal rendering, tables, strikethrough, task lists,
        footnotes, and dollar-delimited math enabled.
    """
    parser = MarkdownIt(
        "commonmark", {"highlight": _highlight_code}, renderer_cls=_TerminalRenderer
    )
    parser.enable(["table", "strikethrough"])
    parser.use(dollarmath_plugin)
    # dollarmath installs its own `math_*` render rules on the renderer instance,
    # which shadow the _TerminalRenderer methods; re-register ours so math spans
    # render as in-memory images rather than the plugin's literal `<span>`s.
    parser.add_render_rule("math_inline", _TerminalRenderer.math_inline)
    parser.add_render_rule("math_inline_double", _TerminalRenderer.math_inline)
    parser.add_render_rule("math_block", _TerminalRenderer.math_block)
    parser.add_render_rule("math_block_label", _TerminalRenderer.math_block)
    parser.use(tasklists_plugin, enabled=True)
    parser.use(footnote_plugin)
    return parser


#: One parser per thread. ``_TerminalRenderer`` keeps per-document state on the
#: instance, so a shared parser would race when streaming renders run on a
#: worker thread (``asyncio.to_thread``).
_PARSER_TLS = threading.local()


def _parser() -> MarkdownIt:
    """Return this thread's parser, creating it on first use.

    Returns:
        A thread-local ``MarkdownIt`` instance.
    """
    parser: MarkdownIt | None = getattr(_PARSER_TLS, "parser", None)
    if parser is None:
        parser = _build_parser()
        _PARSER_TLS.parser = parser
    return parser


def render_markdown(text: str) -> str:
    """Render markdown to terminal-style inline HTML for QML rich text.

    Args:
        text: The markdown source.

    Returns:
        An HTML fragment with inline styles (no CSS classes, no scripts).
    """
    if not text:
        return ""
    return _sanitize(_parser().render(text))


# ------------------------------------------------------------------
#  Incremental streaming renderer
# ------------------------------------------------------------------

_LIST_MARKER_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d{1,9}[.)])(?:\s|$)")
_FENCE_MARKER_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,}|\$\$)")


def _is_balanced_math_line(line: str) -> bool:
    """Return whether a ``$$`` line is self-contained.

    Used by the incremental scanner so a single-line ``$$…$$`` equation neither
    opens nor closes a math fence, while a lone ``$$`` delimiter toggles one.

    Args:
        line: A single source line without its terminator.

    Returns:
        ``True`` when the line contains an even number of ``$$`` delimiters.
    """
    return line.count("$$") % 2 == 0


def _is_fresh_block_line(line: str) -> bool:
    """Return whether a line safely begins a new top-level Markdown block.

    Deliberately conservative: a line with leading whitespace (list
    continuation or indented code), a list marker, or a block quote is never a
    boundary. Committing there could renumber an ordered list, merge/split a
    loose list, or detach an indented block from its parent.

    Args:
        line: A single source line without its terminator.

    Returns:
        ``True`` when the line starts a block independent of the prefix.
    """
    if not line or line[0] in " \t":
        return False
    return not (line.startswith(">") or _LIST_MARKER_RE.match(line))


class IncrementalMarkdown:
    """Render a growing Markdown document with a committed-prefix cache.

    Completed top-level blocks are rendered once and reused; only the trailing
    partial block is re-rendered on each update. The boundary scan keeps a
    cursor and fence/blank-line state across calls, so each character of the
    source is scanned at most once. Falls back to a full render when the source
    is rewritten (e.g. a regeneration) or no safe block boundary exists.

    Attributes:
        _committed_text: Source prefix already rendered into ``_committed_html``.
        _committed_html: Sanitized HTML for ``_committed_text``.
        _scan_pos: Offset of the first complete line not yet boundary-scanned.
        _fence: Open fence character at ``_scan_pos``, or ``None``.
        _prev_blank: Whether the line before ``_scan_pos`` was blank.
    """

    def __init__(self) -> None:
        """Initialise an empty incremental renderer."""
        self._committed_text = ""
        self._committed_html = ""
        self._scan_pos = 0
        self._fence: str | None = None
        self._prev_blank = False

    def reset(self) -> None:
        """Discard all cached rendering and scan state."""
        self._committed_text = ""
        self._committed_html = ""
        self._scan_pos = 0
        self._fence = None
        self._prev_blank = False

    def render(self, text: str) -> str:
        """Return HTML for ``text``, reusing the committed prefix when possible.

        Args:
            text: The full current Markdown source.

        Returns:
            A sanitized HTML fragment equivalent to ``render_markdown(text)``.
        """
        prefix, tail = self.render_parts(text)
        return prefix + tail

    def render_parts(self, text: str) -> tuple[str, str]:
        """Return the committed-prefix and live-tail HTML for ``text``.

        The prefix covers every complete top-level block already scanned and is
        stable across ticks (it only grows when a new block boundary is
        committed). The tail is the not-yet-committed trailing partial block,
        which changes on every call. Splitting them lets the view keep the
        prefix's rich-text layout cached and re-lay out only the tail, avoiding
        an O(n) re-parse/re-layout of the whole document on every stream tick.

        Args:
            text: The full current Markdown source.

        Returns:
            A ``(prefix_html, tail_html)`` tuple whose concatenation equals
            ``render_markdown(text)``.
        """
        if not text:
            return "", ""
        if not text.startswith(self._committed_text):
            self.reset()
        boundary = self._scan(text)
        if boundary > len(self._committed_text):
            segment = text[len(self._committed_text) : boundary]
            self._committed_html += render_markdown(segment)
            self._committed_text = text[:boundary]
        tail = text[len(self._committed_text) :]
        return self._committed_html, render_markdown(tail)

    def _scan(self, text: str) -> int:
        """Advance the boundary scan over newly completed lines.

        Args:
            text: The full current Markdown source.

        Returns:
            The last safe commit offset seen, or ``0`` when none exists.
        """
        last_nl = text.rfind("\n")
        if last_nl < 0:
            return 0
        scan_end = last_nl + 1
        pos = self._scan_pos
        if pos >= scan_end:
            return 0
        committed_len = len(self._committed_text)
        fence = self._fence
        prev_blank = self._prev_blank
        boundary = 0
        while pos < scan_end:
            nl = text.find("\n", pos)
            line = text[pos:nl]
            stripped = line.strip()
            marker = _FENCE_MARKER_RE.match(line)
            is_math = marker is not None and marker.group(1).startswith("$")
            balanced_math = is_math and _is_balanced_math_line(line)
            if fence is not None:
                if marker and marker.group(1)[0] == fence and not balanced_math:
                    fence = None
                prev_blank = False
            elif marker and not balanced_math:
                fence = marker.group(1)[0]
                prev_blank = False
            elif prev_blank and stripped and pos >= committed_len and _is_fresh_block_line(line):
                boundary = pos
                prev_blank = False
            else:
                prev_blank = stripped == ""
            pos = nl + 1
        self._scan_pos = scan_end
        self._fence = fence
        self._prev_blank = prev_blank
        return boundary
