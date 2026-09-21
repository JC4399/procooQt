# qt.theme — theme & style constants

Source: `src/qt/theme.py`

## Purpose

Terminal-style dark theme for the Procoo Qt UI and the single source of truth
for styling. All colors are hex strings and all radii are zero (square). Python
card and markdown builders import the constants directly, while QML reads them
through the [`Theme`](qt-ui.md) `QObject` exposed as the `Theme` context
property (`Theme.colors.pageBg`, `Theme.metrics.cardRadius`,
`Theme.fontMono`). QML must never hard-code a hex colour.

## Deliverables

- Module-level color constants grouped by UI region (backgrounds, text,
  accents, borders, buttons, bubbles, approval, context banner, chat border,
  toasts, session status, cards, chips, tool-mode badges, toast, drag feedback,
  resize handle, inputs).
- Sizing/font constants (`BUTTON_RADIUS`, `CARD_RADIUS`, `STATUS_DOT_RADIUS`,
  `CONTROL_INDICATOR_SIZE`, `CONTROL_INDICATOR_RADIUS`, `CONTROL_DOT_SIZE`,
  `FONT_MONO`, `FONT_SIZE_BASE`, `FONT_SIZE_MARKDOWN`, `LINE_HEIGHT_BODY`,
  `BUTTON_WIDTH_*`, `WHEEL_SCROLL_STEP`, …).
- Markdown palette constants (`COLOR_MD_*`) consumed by
  [`qt.markdown`](qt-markdown.md); only `COLOR_MD_TEXT` is registered for QML.
- `COLORS: dict[str, str]` — camelCase color-name registry.
- `METRICS: dict[str, int]` — camelCase numeric registry.
- `Theme(QObject)` exposing three constant `Property` values: `colors`,
  `metrics`, `fontMono`.

## Theme categories

| Group | Notable constants |
|---|---|
| Backgrounds | `COLOR_PAGE_BG` (#0d1117), `COLOR_SURFACE_BG`, `COLOR_ELEVATED_BG`, `COLOR_HOVER_BG` |
| Text | `COLOR_TEXT_PRIMARY`, `COLOR_TEXT_SECONDARY`, `COLOR_TEXT_DISABLED` |
| Accents | `COLOR_ACCENT_CYAN/GREEN/AMBER/RED/MAGENTA/BLUE` |
| Borders | `COLOR_BORDER_DEFAULT/LIGHT/STRONG` |
| Buttons | `COLOR_BUTTON_PRIMARY_BG/FG`, `COLOR_BUTTON_APPROVE_BG/FG` |
| Chat bubbles | `COLOR_BUBBLE_USER` / `_BORDER`, `COLOR_BUBBLE_ASSISTANT` / `_BORDER` |
| Approval | `COLOR_APPROVAL_BG`, `COLOR_APPROVAL_BORDER` |
| Context banner | `COLOR_CONTEXT_BANNER_BG/BORDER`, `COLOR_CONTEXT_BANNER_DELTA_BG/BORDER` |
| Toasts | `COLOR_ERROR_SNACKBAR`, `COLOR_WARNING_SNACKBAR` |
| Session status | `COLOR_SESSION_{SELECTED_BG,EMPTY,FINISHED,WAITING,ERROR,RUNNING,FLASH}` |
| Cards | `COLOR_THINKING_*`, `COLOR_TOOL_CALL_*`, `COLOR_TOOL_RESULT_*`, `COLOR_CARD_HEADER_DIVIDER` |
| Chips | `COLOR_CHIP_{PRIMARY,SECONDARY,ALLOW,ASK,BLOCK}_{BG,FG}` |
| Tool modes | `COLOR_TOOL_MODE_{ALLOW,ASK,BLOCK,DEFAULT}_{BG,FG}` |
| Markdown | `COLOR_MD_TEXT` (#eeeeee), `_HEADING`, `_BOLD`, `_ITALIC`, `_CODE`, `_LINK`, `_LIST_MARKER`, `_LIST_NUMBER`, `_QUOTE`, `_RULE` |
| Inputs | `INPUT_BORDER_COLOR`, `INPUT_FOCUSED_BORDER_COLOR`, `INPUT_FILL_COLOR`, `INPUT_CURSOR_COLOR`, `INPUT_TEXT_COLOR` |

Chat card surfaces (`COLOR_BUBBLE_USER`, `COLOR_BUBBLE_ASSISTANT`,
`COLOR_THINKING_BG`, `COLOR_TOOL_CALL_BG`, `COLOR_TOOL_RESULT_BG`) all alias
`COLOR_PAGE_BG`, so cards blend into the chat canvas and read as outlines.

## Registry naming

`COLORS` and `METRICS` map each `UPPER_SNAKE` constant to a camelCase QML key,
so Python and QML agree on one vocabulary:

```python
COLORS["pageBg"]              # "#0d1117"
COLORS["sessionWaiting"]      # COLOR_ACCENT_AMBER
METRICS["cardRadius"]         # 0
METRICS["fontSizeBase"]       # 12
METRICS["fontSizeMarkdown"]   # 12
```

Font metrics are **point** sizes (QML uses `font.pointSize`). Every non-markdown
text element uses `fontSizeBase` (12 pt); `fontSizeMarkdown` (12 pt) applies only
to chat markdown bodies rendered by `CardBase.qml`. `LINE_HEIGHT_BODY` (`125%`)
is the CSS line height applied to every chat card body — plain-text `<pre>`
blocks and markdown paragraphs/lists/code. The `fontSizeGutter`,
`fontSizeTree`, `fontSizeBody`, `fontSizeLabelSmall` and `fontSizeTitle*` entries
remain registered but unused.

`WHEEL_SCROLL_STEP` (120 px) is the distance the chat list moves per discrete
mouse-wheel notch; `ChatPanel.qml` reads it as `Theme.metrics.wheelScrollStep`.

`CONTROL_INDICATOR_SIZE` (12), `CONTROL_INDICATOR_RADIUS` (2) and
`CONTROL_DOT_SIZE` (6) define the single shared toggle look — a square
indicator with an accent border and an inner dot. They are consumed by
`FlatIndicator.qml`, the indicator reused by `FlatCheckBox.qml`,
`FlatRadio.qml` and `AutoScrollToggle.qml`.

Because the properties are `QVariantMap`s, QML reaches them with dot syntax, as
used throughout `src/qml/**`:

```qml
color: Theme.colors.surfaceBg
radius: Theme.metrics.buttonRadius
font.family: Theme.fontMono
```

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, parent: QObject \| None = None) -> None` | `parent` optional Qt parent | `None` | `super().__init__(parent)` | — |
| `@Property(dict, constant=True) def colors(self) -> dict[str, str]` | — | The `COLORS` registry | returns the module dict | Read-only from QML |
| `@Property(dict, constant=True) def metrics(self) -> dict[str, int]` | — | The `METRICS` registry | returns the module dict | Read-only from QML |
| `@Property(str, constant=True) def fontMono(self) -> str` | — | `FONT_MONO` family name | returns the constant | Name flagged with `# noqa: N802` for the camelCase property |
