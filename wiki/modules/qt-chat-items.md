# qt.chat_items — chat card item builders

Source: `src/qt/chat_items.py`

## Purpose

Build role-keyed chat-item dictionaries for `ChatListModel`, rendered by the QML
card delegates under `src/qml/cards/`. Builders never touch QML objects. Body HTML is
pre-rendered here: escaped `<pre>` for user/tool-result, `render_markdown` for
thinking/response, and `highlight_yaml_html` over the YAML serializer for
tool calls.

## Deliverables

- `KIND_*` constants: `KIND_USER`, `KIND_THINKING`, `KIND_RESPONSE`,
  `KIND_TOOL_CALL`, `KIND_TOOL_RESULT`, `KIND_CONTEXT_BANNER`.
- `make_item` — generic `ChatRole`-keyed dictionary builder.
- Item builders: `build_user_item`, `build_thinking_item` /
  `build_thinking_pending_item`, `build_response_item` /
  `build_response_pending_item`, `build_tool_call_item` /
  `build_tool_call_pending_item`, `build_tool_result_item` /
  `build_tool_result_pending_item`.
- Shared card helpers: `_card_item`, `_token_text`, `_plain_body`.
- Tool-argument helpers: `_parse_tool_arguments`, `_yaml_quote`,
  `_format_yaml_value`, `_to_yaml_string`.

## Shared card anatomy

Every builder funnels through `_card_item` → `make_item`, the single place that
knows the role layout, the `"{n} tk"` token format, and the collapsed/pending
defaults. The QML side renders any item through `src/qml/cards/CardBase.qml`:

```
header row (icon + title [+ mode badge] [+ subtitle]) ── token text ── collapse arrow
  ─────────────────────────────── (divider)
body (rich-text HTML) or BusyIndicator while isPending
```

`CardBase.qml` is the single header implementation; each concrete card
(`UserCard.qml`, `ThinkingCard.qml`, …) only sets `iconGlyph`, accent colours,
border style, and vertical padding. `CardBase` exposes `padTop`/`padBottom`
(default 8 px; `UserCard` uses 24 px) which the `ChatPanel.qml` delegate applies
as margins outside the card border to space cards apart; `ContextBanner.qml`
mirrors the same 8 px default. Pending variants keep
the same header and set `isPending`; `CardBase` shows a `BusyIndicator` only while
pending with no body yet, so a streaming thinking/response card renders its
growing body instead of the spinner. The body `TextEdit` uses
`Theme.colors.mdText` for markdown kinds (`thinking`/`response`) and
`Theme.colors.textPrimary` otherwise, and opens clicked links with
`Qt.openUrlExternally`. `ChatPanel.qml` binds each delegate
from the `ChatListModel` roles (`kind`, `title`, `body_html`, `token_text`,
`mode`, `is_pending`, `tool_name`, `sections`, `is_delta`).

The collapsible body height in `CardBase.qml` is only animated when the user
clicks the header (`bodyHost.animateBody` gates the `Behavior`); creation and
streaming-driven height growth apply instantly, so they do not churn the scroll
position.

The chat list in `ChatPanel.qml` is a **non-virtualized** `Flickable` + `Column` +
`Repeater`, not a `ListView`: every card is instantiated so `contentHeight` is
exact. A virtualized `ListView` was tried and abandoned — with these
variable-height cards its `contentHeight` is only an estimate, and
`positionViewAtEnd()` against that estimate shifted `originY` without bound
(runaway scrolling, a jumping scrollbar, and a middle-of-viewport landing).
Auto-scroll sets `contentY = contentHeight - height` through a 30 ms debounce
`Timer` guarded by `!moving && !flicking`, following the newest card while
`autoScrollToggle.checked || followTail`; `followTail` tracks `atYEnd` on
`onContentYChanged`. If the user scrolls up while the toggle is on, the toggle
calls `deactivateWithBlink()`: it switches `checked` off, blinks twice, then
hides itself in the normal unchecked state. `boundsBehavior:
Flickable.StopAtBounds` prevents dragging past the last card.

Mouse-wheel scrolling is handled by a `WheelHandler` on the chat `Flickable`,
because Qt exposes no wheel-step property and the native platform step is much
smaller: high-resolution or trackpad `pixelDelta` is applied verbatim, while
discrete notches step by `Theme.metrics.wheelScrollStep` (120 px). Unlike a
naive offset, the handler **clamps** the new `contentY` to
`[0, contentHeight - height]` instead of calling `returnToBounds()`, so it never
overshoots the true bounds and cannot show blank space beyond the first/last
card. `onContentYChanged` updates `followTail` from `atYEnd`, so wheeling up
stops auto-follow (deactivating an active `autoScrollToggle` via
`deactivateWithBlink()`) and wheeling back to the end resumes it. A vertical
`ScrollBar` (`ScrollBar.AsNeeded`) provides feedback and drag-scroll.

## Card types

| Card | `kind` | QML delegate | Border | Header | Body |
|---|---|---|---|---|---|
| User | `user` | `UserCard.qml` | 3px green | `❯` + "User" | escaped `<pre>` |
| Thinking | `thinking` | `ThinkingCard.qml` | top/bottom blue | `◌` + "Thinking" | `render_markdown` (streamed while pending) |
| Response | `response` | `ResponseCard.qml` | 3px amber | `◆` + "Response" | `render_markdown` (streamed while pending) |
| Tool call | `tool_call` | `ToolCallCard.qml` | top/bottom magenta | `⚙` + "Tool Call" + mode badge | `highlight_yaml_html` |
| Tool result | `tool_result` | `ToolResultCard.qml` | top/bottom magenta | `▤` + "Tool Result" (subtitle = tool name) | escaped `<pre>` |
| Context banner | `context_banner` | `ContextBanner.qml` | neutral / orange delta | title + section count | structured sections (JSON) |

Tool-call cards carry `mode` (allow/ask/block) and `tool_name`; result cards
carry `tool_name` and `tool_call_id`. Pending result cards set `tool_call_id` so
`ChatListModel.find_pending_result` can locate and replace the card.

## Body HTML generation

1. **User / tool result** — `_plain_body` escapes the text with `html.escape`
   and wraps it in
   `<pre style="white-space:pre-wrap;margin:0;font-family:Sarasa Fixed TC;line-height:125%">`
   (the `font-family` keeps Qt's `<pre>` from substituting its system monospace
   font, matching `Theme.fontMono`; `line-height` comes from
   `Theme.LINE_HEIGHT_BODY` so plain text matches markdown leading).
2. **Thinking / response** — `render_markdown` returns sanitized, inline-styled
   HTML for a QML `TextEdit.RichText` (terminal-style colours, CSS bordered
   tables, clickable links; see [`qt-markdown`](qt-markdown.md)).
3. **Tool call** — `_to_yaml_string` serializes `{name, mode, arguments}` and
   `highlight_yaml_html` colourises it into a `<pre>` HTML block.

## Function Reference

### Item construction

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `make_item(kind, *, title="", body_html="", token_text="", collapsed=False, is_pending=False, mode="", tool_name="", tool_call_id="", sections="", is_delta=False) -> dict[int, object]` | `kind` — `KIND_*`; `title`/`body_html`/`token_text` — header and body; `collapsed`/`is_pending` — defaults; `mode`/`tool_name`/`tool_call_id`/`sections`/`is_delta` — tool and banner fields | role-keyed dict (`int(ChatRole.*)` → value) | Maps every argument onto its `ChatRole` key | None |
| `_card_item(kind, *, title, body_html="", token_count=0, is_pending=False, mode="", tool_name="", tool_call_id="") -> dict[int, object]` | Card fields with a raw `token_count` | role-keyed dict | Calls `make_item` with `token_text=_token_text(token_count)` | None |
| `_token_text(token_count: int) -> str` | `token_count` | `"42 tk"` | f-string format | None |
| `_plain_body(text: str) -> str` | `text` | escaped `<pre>` block | `html.escape` into `<pre style="white-space:pre-wrap;margin:0;font-family:…;line-height:125%">` | None |

### Item builders

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `build_user_item(text: str) -> dict[int, object]` | `text` | role-keyed dict | `_card_item(KIND_USER, title="User", body_html=_plain_body(text))` | None |
| `build_thinking_item(text: str, *, token_count=0) -> dict[int, object]` | `text`; `token_count` | role-keyed dict | Body = `render_markdown(text)`, title "Thinking" | None |
| `build_thinking_pending_item(text="", *, token_count=0) -> dict[int, object]` | `text` — partial streamed content; `token_count` | role-keyed dict | Body = `render_markdown(text)`, title "Thinking", `is_pending=True` | None |
| `build_response_item(text: str, *, token_count=0) -> dict[int, object]` | `text`; `token_count` | role-keyed dict | Body = `render_markdown(text)`, title "Response" | None |
| `build_response_pending_item(text="", *, token_count=0) -> dict[int, object]` | `text` — partial streamed content; `token_count` | role-keyed dict | Body = `render_markdown(text)`, title "Response", `is_pending=True` | None |
| `build_tool_call_item(entry: dict, *, token_count=0) -> dict[int, object]` | `entry` — `{name, mode, arguments}` | role-keyed dict | `_to_yaml_string` → `highlight_yaml_html`; stores `mode` + `tool_name` | None |
| `build_tool_call_pending_item(name: str, mode: str, token_count=0) -> dict[int, object]` | `name`; `mode`; `token_count` | role-keyed dict | `is_pending=True`, keeps `mode`/`tool_name` | None |
| `build_tool_result_item(name: str, content: str, *, token_count=0) -> dict[int, object]` | `name`; `content`; `token_count` | role-keyed dict | Body = `_plain_body(content)`, stores `tool_name` | None |
| `build_tool_result_pending_item(name: str, tool_call_id="", token_count=0) -> dict[int, object]` | `name`; `tool_call_id`; `token_count` | role-keyed dict | `is_pending=True`, stores `tool_call_id` for later swap | None |

### Tool-argument parsing and YAML formatting

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_parse_tool_arguments(tc: dict) -> dict \| list` | `tc` — tool_call with `function.arguments` (JSON string or raw dict/list) | parsed dict/list, or `{}` | Returns raw dict/list as-is; otherwise `json.loads` and keeps dict/list; failures yield `{}` | None (exceptions suppressed) |
| `_yaml_quote(value: str) -> str` | `value` | double-quoted escaped scalar | Escapes `\`, `"`, `\n`, `\t`, `\r` | None |
| `_format_yaml_value(value: object, indent: int) -> list[str]` | `value` — dict/list/str/int/float/bool/None; `indent` | indented YAML lines | Renders dicts, lists, multiline literal blocks (`\|`), quoted scalars, numbers, booleans, null | None |
| `_to_yaml_string(entry: dict) -> str` | `entry` — `{name, mode, arguments}` | YAML string | Parses string args, emits `name:`/`mode:`/`arguments:` then `_format_yaml_value(args, 2)` | None |

## Related

- [`qt-context-banner`](qt-context-banner.md) — banner items built on `make_item`.
- [`qt-skill-controller`](qt-skill-controller.md) — appends the delta context banner and rebuilds the chat display.
