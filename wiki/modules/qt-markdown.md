# qt.markdown — Markdown → inline-styled HTML

Source: `src/qt/markdown.py`

## Purpose

Render untrusted LLM Markdown into a sanitized HTML fragment for QML rich-text
surfaces (`TextEdit.RichText` in thinking/response cards). It uses
`markdown-it-py` for the CommonMark grammar plus tables, strikethrough, task
lists, and footnotes, and `pygments` for fenced code blocks. Because the source
is model output, the fragment is stripped of scripts, event handlers, and
`javascript:` URLs before it reaches QML.

## Deliverables

- `render_markdown(text) -> str` — sanitized, inline-styled HTML fragment.
- Module-level renderer `_MD` (configured `MarkdownIt` instance).
- Module-level pygments formatter `_FORMATTER`.

## Steps / Flow

### `render_markdown`

1. Return `""` for empty input.
2. `_MD.render(text)` — parse Markdown and emit HTML; fenced code blocks go
   through `_highlight_code`.
3. `_sanitize(fragment)` — drop `<script>`/`<style>` blocks, `on*` attributes,
   and `javascript:` URLs.
4. Return the sanitized fragment.

### `_highlight_code`

1. If a language hint matches a pygments lexer, use it.
2. Otherwise `guess_lexer(code)`.
3. Return `highlight(...)` output, or `""` when no lexer is found (the renderer
   then falls back to plain escaped code).

### `_sanitize`

1. `_SCRIPT_STYLE_RE` removes `<script>…</script>` and `<style>…</style>`.
2. `_EVENT_ATTR_RE` removes inline `on*="…"` handlers.
3. `_JS_URL_RE` removes `href`/`src` values beginning with `javascript:`.

## Markdown-it-py configuration

| Setting | Value | Effect |
|---|---|---|
| Preset | `"commonmark"` | Base CommonMark grammar |
| `highlight` | `_highlight_code` | pygments hook for fenced code |
| `enable(["table", "strikethrough"])` | — | GFM tables and `~~strike~~` |
| `tasklists_plugin(enabled=True)` | — | `- [ ]` / `- [x]` lists |
| `footnote_plugin` | — | `[^1]` references and definitions |

Pygments formatter: `HtmlFormatter(nowrap=True, noclasses=True, style="monokai")`
— `noclasses=True` inlines the colour styles (no CSS classes), so QML needs no
stylesheet; `nowrap=True` omits the outer `<pre>` wrapper.

## Function Reference

### `render_markdown`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def render_markdown(text: str) -> str` | `text` — Markdown source | Sanitized HTML fragment | Empty check → `_MD.render` → `_sanitize` | None; pure |

### `_highlight_code`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def _highlight_code(code: str, lang: str, _attrs: str) -> str` | `code` — raw code; `lang` — fence hint; `_attrs` — unused | Inline-styled HTML, or `""` to fall back | `get_lexer_by_name` → fallback `guess_lexer` → `highlight` | Catches `pygments.util.ClassNotFound` |

### `_sanitize`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def _sanitize(fragment: str) -> str` | `fragment` — rendered HTML | Sanitized HTML | Script/style → event attrs → `javascript:` URLs | None |

### Module constants

| Name | Purpose |
|---|---|
| `_FORMATTER` | pygments `HtmlFormatter(nowrap=True, noclasses=True, style="monokai")` |
| `_SCRIPT_STYLE_RE` | `<script>` / `<style>` block matcher |
| `_EVENT_ATTR_RE` | inline `on*` attribute matcher |
| `_JS_URL_RE` | `javascript:` `href`/`src` matcher |

## See also

- [qt-yaml-highlight](qt-yaml-highlight.md) — the sibling tokenizer for tool-call
  argument YAML.
- [qt-models](qt-models.md) — `ChatListModel` stores the rendered HTML in
  `ChatRole.BODY_HTML`.
