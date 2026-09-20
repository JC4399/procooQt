# qt.yaml_highlight — YAML → inline-styled HTML

Source: `src/qt/yaml_highlight.py`

## Purpose

A YAML tokenizer. It turns tool-call argument YAML into a `<pre>` block of
inline-styled spans so QML `TextEdit.RichText` renders syntax colours. It handles
comment lines, `key:` mapping lines, list items, nested indentation, and inline
string/number/boolean detection.

## Deliverables

- `highlight_yaml_html(text) -> str` — an inline-styled HTML `<pre>` block.

## Steps / Flow

### `highlight_yaml_html`

1. Split `text` on line boundaries (`splitlines`).
2. Tokenize each line with `_tokenize_line`.
3. Join the line fragments with `\n`.
4. Wrap in
   `<pre style="white-space:pre-wrap;margin:0;font-family:Sarasa Fixed TC;line-height:125%">…</pre>`
   (`pre-wrap` preserves indentation while still wrapping long values; the
   explicit family keeps Qt's system monospace out, and `line-height` uses
   `Theme.LINE_HEIGHT_BODY`).

### `_tokenize_line`

1. Empty line → `""`.
2. Line whose first non-space char is `#` → whole line in
   `COLOR_TEXT_SECONDARY`, italic.
3. `_YAML_LIST_KEY_VALUE` (`- key: value`) → `_build_line_html`.
4. `_YAML_LIST_VALUE` (`- value`) → `_build_simple_html`.
5. `_YAML_KEY_VALUE` (`key: value`) → `_build_line_html`.
6. Otherwise → `_plain` (HTML-escaped, no span).

### `_highlight_value`

1. Collect matches from all value patterns (`_STRING_DQ`, `_STRING_SQ`,
   `_BOOLEAN`, `_NUMBER`), sorted by start position and longest-first.
2. Emit plain text for gaps, styled spans for matches.
3. Emit the trailing plain remainder.

## Colours

Colors come from `qt.theme` and are applied via `_styled` inline spans.

| Token | Colour | Style |
|---|---|---|
| Comment (`#…`) | `COLOR_TEXT_SECONDARY` | italic |
| Key (`key`) | `COLOR_ACCENT_MAGENTA` | — |
| Colon / list dash | `COLOR_ACCENT_BLUE` | — |
| String (`"…"` / `'…'`) | `COLOR_ACCENT_GREEN` | — |
| Boolean (`true`/`false`/`yes`/`no`/`null`/`~`) | `COLOR_ACCENT_CYAN` | bold (`600`) |
| Number | `COLOR_ACCENT_CYAN` | — |

## Function Reference

### `highlight_yaml_html`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def highlight_yaml_html(text: str) -> str` | `text` — YAML source | HTML `<pre>` block | Split → tokenize each line → join → wrap | None; pure |

### Private helpers

| Function | Signature | Purpose |
|---|---|---|
| `_styled` | `def _styled(text: str, color: str, *, italic: bool = False, bold: bool = False) -> str` | wrap HTML-escaped text in a `color:` span |
| `_plain` | `def _plain(text: str) -> str` | HTML-escape text that inherits the surrounding colour |
| `_tokenize_line` | `def _tokenize_line(line: str) -> str` | classify and highlight one line |
| `_build_line_html` | `def _build_line_html(indent: str, dash: str, key: str, colon: str, value: str) -> str` | key-value line (optional list dash) |
| `_build_simple_html` | `def _build_simple_html(indent: str, dash: str, value: str) -> str` | list item without a key |
| `_highlight_value` | `def _highlight_value(value: str) -> str` | inline string/number/boolean detection |

### Compiled patterns

| Name | Matches |
|---|---|
| `_YAML_LIST_KEY_VALUE` | `^(\s*)(-\s)?([\w.-]+)(\s*:\s*)(.*)$` |
| `_YAML_LIST_VALUE` | `^(\s*)(-\s)(.*)$` |
| `_YAML_KEY_VALUE` | `^(\s*)([\w.-]+)(\s*:\s*)(.*)$` |
| `_STRING_DQ` / `_STRING_SQ` | double/single-quoted strings with escapes |
| `_NUMBER` | `\b(\d+\.?\d*)\b` |
| `_BOOLEAN` | `\b(true\|false\|yes\|no\|null\|~)\b` (case-insensitive) |

## See also

- [qt-markdown](qt-markdown.md) — Markdown renderer for thinking/response bodies.
- [qt-models](qt-models.md) — tool-call cards carry this HTML in
  `ChatRole.BODY_HTML`.
