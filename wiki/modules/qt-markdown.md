# qt.markdown — terminal-style Markdown → inline HTML

Source: `src/qt/markdown.py`

## Purpose

Render untrusted LLM Markdown into a sanitized HTML fragment for the QML
rich-text surfaces (`TextEdit.RichText` in the response card; the thinking card
renders escaped plain text instead). The
output mimics a TUI markdown pager rather than a browser: syntax marks are
concealed, every element gets an explicit colour from the
[`qt.theme`](qt-theme.md) markdown palette, block quotes get a drawn left
border, lists use literal monospace markers with hanging indents, and tables are
rendered as CSS tables with collapsed borders. `markdown-it-py` supplies the CommonMark
grammar (plus tables, strikethrough, task lists, footnotes, and dollar-delimited
LaTeX math); `pygments` highlights fenced code blocks. Math spans are rasterised
in memory by [`qt.latex`](qt-latex.md) and inlined as `data:` URI images, so no
temporary files are written. Because the source is model output, the fragment
is stripped of scripts, event handlers, and unsafe URL schemes before it
reaches QML.

## Deliverables

- `render_markdown(text) -> str` — sanitized, terminal-styled HTML fragment.
- `IncrementalMarkdown` — a per-card renderer that caches the committed HTML of
  a growing streaming document and re-renders only the trailing block. Its
  `render_parts(text)` returns the committed prefix and the live tail
  separately, so the view can keep the prefix's rich-text layout cached and
  re-lay out only the tail on each stream tick.
- `_TerminalRenderer(RendererHTML)` — the token renderer implementing the
  terminal look.
- `_MarkdownCodeStyle(Style)` and the thread-local `_FORMATTER_TLS` / `_formatter()`
  — pygments style matching the palette, with `noclasses=True` inline colours;
  the formatter is per-thread because each chat renders on its own worker thread.
- `_build_parser()` / `_parser()` and the thread-local `_PARSER_TLS` — one
  `MarkdownIt` instance per thread (streaming renders run on worker threads).
- `math_inline` / `math_block` render rules — delegate to
  [`qt.latex.render_math_fragment`](qt-latex.md) and fall back to the literal
  source when an expression cannot be rasterised.
- Helpers `_safe_href`, `_sanitize`, `_highlight_code`; the boundary helpers
  `_is_fresh_block_line` / `_is_balanced_math_line`; and on the renderer,
  `_cell_open` / `_CELL_STYLE`.

## Steps / Flow

### `render_markdown`

1. Return `""` for empty input.
2. `_parser().render(text)` — parse Markdown and render with
   `_TerminalRenderer`; fenced code blocks go through `_highlight_code`.
3. `_sanitize(fragment)` — drop `<script>`/`<style>` blocks, `on*` attributes,
   and `javascript:` URLs.
4. Return the sanitized fragment.

### Thread-local parser

`_TERMINAL` state (`_TerminalRenderer._lists` / `_items` / `_links`) lives on the
renderer instance, so a single shared parser would race when streaming renders
run on a per-chat worker thread. `_parser()` lazily builds and caches one
`MarkdownIt` per thread in `_PARSER_TLS`; the pygments formatter is likewise
per-thread (`_FORMATTER_TLS`), so concurrent chat renders are safe.

### Incremental streaming renderer (`IncrementalMarkdown`)

1. `render_parts(text)` — if `text` does not start with the committed prefix
   (e.g. a regeneration), `reset()`.
2. `_scan(text)` advances a persisted cursor (`_scan_pos`, `_fence`,
   `_prev_blank`) over only the newly completed lines, returning the last safe
   commit offset: the start of a line that follows a blank line at top level
   (outside a fence) and begins an independent block.
3. When a new boundary exists, render only the newly committed segment and
   append it to `_committed_html`; then render the trailing partial block.
4. Return `(_committed_html, render_markdown(tail))` — whose concatenation
   equals `render_markdown(text)` but is O(delta) per tick instead of O(total):
   each source character is boundary-scanned once. `render(text)` is a thin
   wrapper returning the concatenation for callers that need a single string.

`_is_fresh_block_line` is deliberately conservative: a line with leading
whitespace, a list marker, or a block quote is never a boundary, because
committing there could renumber an ordered list, merge/split a loose list, or
detach an indented block. `_FENCE_MARKER_RE` parity prevents splitting inside a
fenced code block, and `_is_balanced_math_line` keeps a multi-line `$$…$$`
display equation whole (a single-line `$$…$$` is self-contained and never opens
a fence).

### `_TerminalRenderer.render`

1. `_reset()` — clear list/item/link state (the renderer instance is reused
   across documents).
2. `super().render(...)` — dispatch each token to a rule; `inline` tokens go to
   the inherited `renderInline`, so each table cell's inline content is emitted
   directly inside its `<th>`/`<td>`.

### Inline rules

| Token | Output |
|---|---|
| `text` | escaped text |
| `softbreak` / `hardbreak` | newline / `<br>` |
| `strong_*` | `<b><font color="#f5a742">` … |
| `em_*` | `<i><font color="#e5c07b">` … |
| `s_*` | `<s>` … `</s>` |
| `code_inline` | `<font color="#7fd88f">` |
| `link_open` / `link_close` | `<a href>` + `<u><font color="#56b6c2">`; unsafe URLs suppressed (a flag stack keeps the close tag balanced) |
| `image` | alt text (or src) as a cyan underlined link label |
| `math_inline` | `<img>` backed by a [`qt.latex`](qt-latex.md) `data:` URI; literal `$…$` when rendering fails |
| `html_inline` | `[x]`/`[ ]` for task-list checkboxes, otherwise dropped |
| `html_block` | dropped |

### Block rules

| Token | Output |
|---|---|
| `heading_*` | `<p>` in `COLOR_MD_HEADING`, bold, with a one-line bottom margin; `h1` also underlined (no font-size change) |
| `paragraph_*` | `<p style="margin:0 0 12px 0">` (a blank line in the source renders as one visible empty line); a list item's first paragraph becomes its marker `<div>` |
| `blockquote_*` | two-cell `<table>`: a 2px background-filled stripe cell + padded italic yellow content (Qt Quick does not paint `border-left`) |
| `hr` | grey rule |
| `fence` | `<pre>` with a one-line bottom margin, grey ```` ```lang ```` fences around pygments-highlighted code |
| `code_block` | plain `<pre>` with a one-line bottom margin |
| `math_block` | centred `<div>` wrapping the [`qt.latex`](qt-latex.md) image; escaped `<pre>` when rendering fails |
| `bullet_list_*` / `ordered_list_*` / `list_item_*` | literal `-`/`1.` markers, coloured and hanging-indented |
| `table_*`, `thead/tbody/tr/th/td` | CSS `<table border="1">` with `border-color`, a one-line bottom margin; collapsed grey grid; alignment from markdown column hints |

Every body block carries `line-height:125%` from `Theme.LINE_HEIGHT_BODY`, so
markdown text matches the plain-text card bodies. Headings, paragraphs, list
marker `<div>`s, block quote cells, and code `<pre>`s all include it. Top-level
paragraphs, headings, fenced/indented code blocks, and tables additionally carry
a `_BLANK_LINE_PX` (12px) bottom margin, so a blank line between two blocks
renders as a single visible empty line.

### Lists

Each `list_item_open` stages a `_ItemCtx` (marker HTML, margin, negative
`text-indent`). The marker is emitted when the item's first paragraph opens; a
paragraph-less item is flushed by `_flush_pending_marker` at a nested list or
at `list_item_close`. `_CHAR_PX` (a half-em estimate from
`FONT_SIZE_MARKDOWN`) converts marker columns to pixels for the hanging indent;
Qt font metrics are deliberately not queried because no `QGuiApplication`
exists at render time in headless contexts.

### Tables

`table_open` emits
`<table border="1" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border-color:#5c6370;margin:0 0 12px 0">`
and each row is a plain `<tr>`. `th_open`/`td_open` call `_cell_open`, which
applies `_CELL_STYLE` (`padding:4px; line-height:125%`) and appends the column
alignment that `markdown-it-py` puts on the cell token's `style` attribute. Cell
inline content is rendered normally, so bold/links/code inside cells keep their
styling.

Qt Quick's `TextEdit` has two quirks that drove this design, both verified by
rendering through a real `QQuickView`:

- CSS `border` on `<td>`/`<th>` is ignored, but the legacy table `border`
  attribute is honored and recoloured by CSS `border-color`.
- `border-left` on a cell is likewise ignored, so block quotes use a narrow
  background-filled stripe cell instead.

### `_highlight_code`

1. If a language hint matches a pygments lexer, use it.
2. Otherwise `guess_lexer(code)`.
3. Return `highlight(...)` output, or `""` when no lexer is found (the renderer
   then falls back to plain escaped code).

### `_sanitize` / `_safe_href`

1. `_SCRIPT_STYLE_RE` removes `<script>…</script>` and `<style>…</style>`.
2. `_EVENT_ATTR_RE` removes inline `on*="…"` handlers.
3. `_JS_URL_RE` removes `href`/`src` values beginning with `javascript:`.
4. `_safe_href` rejects `javascript:`/`data:`/`vbscript:` links up front so the
   anchor tags stay balanced.

## Markdown-it-py configuration

| Setting | Value | Effect |
|---|---|---|
| Preset | `"commonmark"` | Base CommonMark grammar |
| `highlight` | `_highlight_code` | pygments hook for fenced code |
| `renderer_cls` | `_TerminalRenderer` | Terminal-style token rendering |
| `enable(["table", "strikethrough"])` | — | GFM tables and `~~strike~~` |
| `dollarmath_plugin` | — | `$…$` inline / `$$…$$` display LaTeX math |
| `tasklists_plugin(enabled=True)` | — | `- [ ]` / `- [x]` lists |
| `footnote_plugin` | — | `[^1]` references and definitions |

`dollarmath_plugin` installs its own `math_inline`/`math_block` render rules on
the renderer *instance* (via `MarkdownIt.add_render_rule`), which shadow the
`_TerminalRenderer` methods of the same name. `_build_parser` therefore
re-registers `_TerminalRenderer.math_inline` / `math_block` after applying the
plugin, so math spans render as images rather than the plugin's literal
`<span class="math …">` wrappers.

## Function Reference

### Module API

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def render_markdown(text: str) -> str` | `text` — Markdown source | Sanitized HTML fragment | Empty check → `_parser().render` → `_sanitize` | None; pure |
| `def _build_parser() -> MarkdownIt` | — | Configured parser | `MarkdownIt` → `enable(table, strikethrough)` → tasklists → footnotes | Expensive; cached per thread |
| `def _parser() -> MarkdownIt` | — | Thread-local parser | Lazy build into `_PARSER_TLS` | None |
| `class IncrementalMarkdown` | — | Streaming renderer | `render_parts` commits safe prefixes, renders only the tail | Caches committed source + HTML + scan cursor |
| `def IncrementalMarkdown.render(text: str) -> str` | `text` — full growing source | Sanitized HTML fragment | Concatenate `render_parts` | Mutates committed prefix + scan state |
| `def IncrementalMarkdown.render_parts(text: str) -> tuple[str, str]` | `text` — full growing source | `(prefix_html, tail_html)` | reset-on-rewrite → `_scan` → render segment + tail | Mutates committed prefix + scan state |
| `def IncrementalMarkdown._scan(text: str) -> int` | `text` — full growing source | Commit offset or `0` | Walk only newly completed lines, tracking fence/blank state | Advances `_scan_pos`/`_fence`/`_prev_blank` |
| `def IncrementalMarkdown.reset() -> None` | — | `None` | blank committed source/HTML and scan cursor | — |
| `def _is_fresh_block_line(line: str) -> bool` | source line | Bool | Reject indented/list/quote lines | None; pure |
| `def _is_balanced_math_line(line: str) -> bool` | source line | Bool | Even `$$` count, so a single-line `$$…$$` neither opens nor closes a math fence | None; pure |
| `def math_inline(self, tokens, idx, options, env) -> str` | inline token | `qt.latex` `<img>` or literal `$…$` | `render_math_fragment(display=False)` | Rasterises on miss |
| `def math_block(self, tokens, idx, options, env) -> str` | block token | centred `<div><img/>` or escaped `<pre>` | `render_math_fragment(display=True)` | Rasterises on miss |
| `def _highlight_code(code: str, lang: str, _attrs: str) -> str` | `code` — raw code; `lang` — fence hint; `_attrs` — unused | Inline-styled HTML, or `""` to fall back | `get_lexer_by_name` → fallback `guess_lexer` → `highlight` | Catches `pygments.util.ClassNotFound` |
| `def _sanitize(fragment: str) -> str` | `fragment` — rendered HTML | Sanitized HTML | Script/style → event attrs → `javascript:` URLs | None |
| `def _safe_href(url: str) -> str` | `url` — raw link target | Safe URL or `""` | Regex scheme check | None |

### `_TerminalRenderer`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, parser: object = None) -> None` | `parser` unused (base signature) | `None` | `super().__init__` → `_reset` | Builds rule table via base class |
| `def render(self, tokens, options, env) -> str` | Token stream, options, env | HTML fragment | `_reset` → `super().render` | Mutates instance state |
| `def paragraph_open/close(...)` | — | Marker `<div>` or `<p>` | Emits staged list marker on first paragraph | Reads/writes `_items` |
| `def list_item_open/close(...)` | — | `""` / flushed marker | Stages `_ItemCtx`; flushes paragraph-less items | Reads/writes `_lists`, `_items` |
| `def _flush_pending_marker() -> str` | — | Closed marker `<div>` or `""` | Emits marker for paragraph-less items | Mutates `_items` |
| `def table_open/close(...)` | — | `<table border="1" …>` / `</table>` | Opens `border-collapse` CSS table recoloured via `border-color` | None |
| `def th_open/td_open(...)` | — | Cell `<th>`/`<td>` | `_cell_open` merges padding/line-height style with alignment | None |
| `def th_close/td_close(...)` | — | `</th>` / `</td>` | — | None |
| `def _cell_open(tag, tokens, idx) -> str` | `tag` — `th`/`td`; cell token | Opening cell HTML | `_CELL_STYLE` (`padding`+`line-height`) + token `style` alignment | None |

### Module constants

| Name | Purpose |
|---|---|
| `_FORMATTER_TLS` / `_formatter()` | thread-local pygments `HtmlFormatter(nowrap=True, noclasses=True, style=_MarkdownCodeStyle)` |
| `_PARSER_TLS` | `threading.local` holding one `MarkdownIt` per thread |
| `_LIST_MARKER_RE` | fresh-block guard: rejects ordered/unordered list markers |
| `_FENCE_MARKER_RE` | fenced code / `$$` math marker matcher for boundary fence parity |
| `_is_balanced_math_line` | even-`$$` test so single-line display math is not treated as an open fence |
| `_CHAR_PX` | Estimated monospace cell width for list hanging indents |
| `_BLANK_LINE_PX` | Paragraph/heading bottom margin that renders a source blank line as one empty line |
| `_SCRIPT_STYLE_RE` | `<script>` / `<style>` block matcher |
| `_EVENT_ATTR_RE` | inline `on*` attribute matcher |
| `_JS_URL_RE` | `javascript:` `href`/`src` matcher |
| `_UNSAFE_URL_RE` | unsafe link scheme matcher |

## See also

- [qt-latex](qt-latex.md) — in-memory LaTeX math → `data:` URI images consumed by
  the `math_inline` / `math_block` rules.
- [qt-theme](qt-theme.md) — the `COLOR_MD_*` palette and `FONT_SIZE_MARKDOWN`.
- [qt-yaml-highlight](qt-yaml-highlight.md) — the sibling tokenizer for tool-call
  argument YAML.
- [qt-models](qt-models.md) — `ChatListModel` stores the rendered HTML in
  `ChatRole.BODY_HTML` (frozen prefix) and `ChatRole.BODY_TAIL_HTML` (live
  streaming tail).
