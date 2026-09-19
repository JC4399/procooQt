# qt.highlighter — QSyntaxHighlighter for the code editor

Source: `src/qt/highlighter.py`

## Purpose

A `QSyntaxHighlighter` subclass that gives the QML code editor (in the separate
`EditorWindow`) per-language syntax colouring. It attaches to a QML `TextArea`'s
`QTextDocument` and applies a rule set chosen by `set_language`. Dedicated rule
sets exist for Python, YAML, JSON, Bash, JavaScript, SQL, HTML, CSS, and
Markdown; every other language normalises to a generic `"plain"` set.

## Deliverables

- `CodeHighlighter(QSyntaxHighlighter)` — the highlighter.
- `SUPPORTED_LANGUAGES` — frozen set of recognised language names.
- `_KEYWORD_SETS` / `_COMMENT_TOKENS` — per-language keyword and comment tables.
- `_format(color, *, bold, italic) -> QTextCharFormat` — format factory.
- `_keyword_pattern(keywords) -> QRegularExpression | None` — word-boundary
  alternation builder.

## Steps / Flow

### `set_language`

1. Normalise `language` — keep it only if in `SUPPORTED_LANGUAGES`, else
   `"plain"`.
2. No-op if the normalised name equals the active language.
3. Store it, `_build_rules()`, then `rehighlight()`.

### `highlightBlock`

1. Apply every `(pattern, format)` rule with `globalMatch` +
   `setFormat(start, length, fmt)`.
2. If the language has a comment token, italicise `COLOR_TEXT_SECONDARY` from
   the first occurrence to end of line.

### `_build_rules`

1. Reset `rules`, look up `_COMMENT_TOKENS`.
2. Append keyword rules, literal rules (numbers + strings), and language-specific
   extras.

### Rule construction

| Builder | Rules produced |
|---|---|
| `_keyword_rules` | one alternation rule over the language's keyword set, `COLOR_ACCENT_MAGENTA` bold |
| `_literal_rules` | `\b[0-9]+(\.[0-9]+)?\b` → `COLOR_ACCENT_CYAN`; `"…"\|'…'` → `COLOR_ACCENT_GREEN` |
| `_extra_rules` | Markdown headings/bold/code/links; HTML tags; CSS properties; `plain` list markers; otherwise none |

### Role in the editor

`EditorController.attachHighlighter(area)` reads the QML `TextArea`'s
`textDocument` (`QQuickTextDocument` wrapper → `QTextDocument`), constructs
`CodeHighlighter(document)`, and keeps both wrapper and document alive. On file
load (`_load_file_into_editor`) `set_language(detect_language(filepath))` swaps
the rule set; the highlighter never raises when the document is unavailable.

## Supported languages

| Language | Keywords | Comment token | Extra rules |
|---|---|---|---|
| `python` | `and as assert … yield` | `#` | — |
| `yaml` | `true false null yes no on off` | `#` | — |
| `json` | `true false null` | — | — |
| `bash` | `alias case … while` | `#` | — |
| `javascript` | `async await … yield` | `//` | — |
| `sql` | `ADD ALTER … WHERE` | `--` | — |
| `markdown` | — | — | headings, `**bold**`, `` `code` ``, links |
| `html` | — | — | `</?tag…>` tags |
| `css` | — | — | `property:` names |
| `plain` | — | — | leading `-`/`:` markers (generic fallback) |

## Function Reference

### `CodeHighlighter`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, document: QTextDocument) -> None` | `document` — target text document | — | init `rules`/`language="plain"` → `_build_rules` | Retains no external state |
| `def set_language(self, language: str) -> None` | `language` — desired language | `None` | normalise → no-op if same → rebuild → `rehighlight` | Triggers a document re-highlight |
| `def highlightBlock(self, text: str) -> None` (N802) | `text` — one line | `None` | apply rules + comment tail | Mutates block formats |
| `def _build_rules(self) -> None` | — | `None` | keyword + literal + extra rules | Replaces `self.rules` |
| `def _keyword_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]` | — | zero/one keyword rule | `_keyword_pattern` | — |
| `def _literal_rules() -> list[...]` (`@staticmethod`) | — | number + string rules | — | — |
| `def _extra_rules(self) -> list[...]` | — | language-specific rules | branch on `self.language` | — |

### Module helpers

| Function | Signature | Purpose |
|---|---|---|
| `_format` | `def _format(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat` | build a `QTextCharFormat` |
| `_keyword_pattern` | `def _keyword_pattern(keywords: tuple[str, ...]) -> QRegularExpression \| None` | word-boundary alternation, `None` if empty |

## See also

- [qt-models](qt-models.md) — `FileTreeModel` supplies the editor's file list.
