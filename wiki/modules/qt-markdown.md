# qt.markdown — terminal-style Markdown → inline HTML

Source: `src/qt/markdown.py`

## Purpose

Render untrusted LLM Markdown into a sanitized HTML fragment for the QML
rich-text surfaces (`TextEdit.RichText` in the thinking/response cards). The
output mimics a TUI markdown pager rather than a browser: syntax marks are
concealed, every element gets an explicit colour from the
[`qt.theme`](qt-theme.md) markdown palette, block quotes get a drawn left
border, lists use literal monospace markers with hanging indents, and tables are
rendered as CSS tables with collapsed borders. `markdown-it-py` supplies the CommonMark
grammar (plus tables, strikethrough, task lists, and footnotes); `pygments`
highlights fenced code blocks. Because the source is model output, the fragment
is stripped of scripts, event handlers, and unsafe URL schemes before it
reaches QML.

## Deliverables

- `render_markdown(text) -> str` — sanitized, terminal-styled HTML fragment.
- `_TerminalRenderer(RendererHTML)` — the token renderer implementing the
  terminal look.
- `_MarkdownCodeStyle(Style)` and `_FORMATTER` — pygments style matching the
  palette, with `noclasses=True` inline colours.
- Module-level parser `_MD` (configured `MarkdownIt`).
- Helpers `_safe_href`, `_sanitize`, `_highlight_code`; and on the renderer,
  `_cell_open` / `_CELL_STYLE`.

## Steps / Flow

### `render_markdown`

1. Return `""` for empty input.
2. `_MD.render(text)` — parse Markdown and render with `_TerminalRenderer`;
   fenced code blocks go through `_highlight_code`.
3. `_sanitize(fragment)` — drop `<script>`/`<style>` blocks, `on*` attributes,
   and `javascript:` URLs.
4. Return the sanitized fragment.

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
| `html_inline` | `[x]`/`[ ]` for task-list checkboxes, otherwise dropped |
| `html_block` | dropped |

### Block rules

| Token | Output |
|---|---|
| `heading_*` | `<p>` in `COLOR_MD_HEADING`, bold; `h1` also underlined (no font-size change) |
| `paragraph_*` | `<p style="margin:0">`; a list item's first paragraph becomes its marker `<div>` |
| `blockquote_*` | two-cell `<table>`: a 2px background-filled stripe cell + padded italic yellow content (Qt Quick does not paint `border-left`) |
| `hr` | grey rule |
| `fence` | `<pre>` with grey ```` ```lang ```` fences around pygments-highlighted code |
| `code_block` | plain `<pre>` |
| `bullet_list_*` / `ordered_list_*` / `list_item_*` | literal `-`/`1.` markers, coloured and hanging-indented |
| `table_*`, `thead/tbody/tr/th/td` | CSS `<table border="1">` with `border-color`; collapsed grey grid; alignment from markdown column hints |

Every body block carries `line-height:150%` from `Theme.LINE_HEIGHT_BODY`, so
markdown text matches the plain-text card bodies. Headings, paragraphs, list
marker `<div>`s, block quote cells, and code `<pre>`s all include it.

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
`<table border="1" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border-color:#5c6370;margin:0">`
and each row is a plain `<tr>`. `th_open`/`td_open` call `_cell_open`, which
applies `_CELL_STYLE` (`padding:4px; line-height:150%`) and appends the column
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
| `tasklists_plugin(enabled=True)` | — | `- [ ]` / `- [x]` lists |
| `footnote_plugin` | — | `[^1]` references and definitions |

## Function Reference

### Module API

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def render_markdown(text: str) -> str` | `text` — Markdown source | Sanitized HTML fragment | Empty check → `_MD.render` → `_sanitize` | None; pure |
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
| `_FORMATTER` | pygments `HtmlFormatter(nowrap=True, noclasses=True, style=_MarkdownCodeStyle)` |
| `_CHAR_PX` | Estimated monospace cell width for list hanging indents |
| `_SCRIPT_STYLE_RE` | `<script>` / `<style>` block matcher |
| `_EVENT_ATTR_RE` | inline `on*` attribute matcher |
| `_JS_URL_RE` | `javascript:` `href`/`src` matcher |
| `_UNSAFE_URL_RE` | unsafe link scheme matcher |

## See also

- [qt-theme](qt-theme.md) — the `COLOR_MD_*` palette and `FONT_SIZE_MARKDOWN`.
- [qt-yaml-highlight](qt-yaml-highlight.md) — the sibling tokenizer for tool-call
  argument YAML.
- [qt-models](qt-models.md) — `ChatListModel` stores the rendered HTML in
  `ChatRole.BODY_HTML`.
