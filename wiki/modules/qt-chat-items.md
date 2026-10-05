# qt.chat_items — chat card item builders

Source: `src/qt/chat_items.py`

## Purpose

Build role-keyed chat-item dictionaries for `ChatListModel`, rendered by the QML
card delegates under `src/qml/cards/`. Builders never touch QML objects. Body HTML is
pre-rendered here: escaped `<pre>` for user / tool-result / thinking,
`render_markdown` for response, and `highlight_yaml_html` over the YAML
serializer for tool calls.

## Deliverables

- `KIND_*` constants: `KIND_USER`, `KIND_THINKING`, `KIND_RESPONSE`,
  `KIND_TOOL_CALL`, `KIND_TOOL_RESULT`, `KIND_CONTEXT_BANNER`, `KIND_WAITING`.
- `make_item` — generic `ChatRole`-keyed dictionary builder.
- Item builders: `build_user_item`, `build_waiting_item`, `build_thinking_item` /
  `build_thinking_pending_item`, `build_response_item` /
  `build_response_pending_item`, `build_tool_call_item` /
  `build_tool_call_pending_item`, `build_tool_result_item` /
  `build_tool_result_pending_item`.
- Shared card helpers: `_card_item`, `_token_text`, `_plain_body`,
  `thinking_body`.
- Tool-argument helpers: `_parse_tool_arguments`, `_yaml_quote`,
  `_format_yaml_value`, `_to_yaml_string`.

## Shared card anatomy

Every builder funnels through `_card_item` → `make_item`, the single place that
knows the role layout, the `"{n} tk"` token format, and the collapsed/pending
defaults. The QML side renders any item through `src/qml/cards/CardBase.qml`:

```
header row (icon + title [+ mode badge] [+ subtitle]) ── reload/trash icons ── token text ── collapse arrow
  ─────────────────────────────── (divider)
body (rich-text HTML) or KnightRiderSpinner while isPending```

`CardBase.qml` is the single header implementation; each concrete card
(`UserCard.qml`, `ThinkingCard.qml`, …) only sets `iconGlyph`, accent colours,
border style, and vertical padding. `CardBase` exposes `padTop`/`padBottom`
(default 8 px; `UserCard` uses 24 px) which the `ChatPanel.qml` delegate applies
as margins outside the card border to space cards apart; `ContextBanner.qml`
mirrors the same 8 px default. Pending variants keep
the same header and set `isPending`; `CardBase` shows a `KnightRiderSpinner`
(`src/qml/components/KnightRiderSpinner.qml`) only while pending with no body
yet, so a streaming thinking/response card renders its growing body instead of
the spinner. Spinners keep sweeping whenever they are visible (`running: visible`);
they are not gated on window focus, and the tab status-dot blink
(`model.is_blinking`) likewise keeps pulsing in an unfocused window, resetting the
dot's opacity to `1.0` the moment the blink stops so a finished tab is never left
faded. `CardBase` also exposes `headerVisible` (default `true`); the
headerless `WaitingCard.qml` sets it `false` so the pre-response placeholder is
just a grey scanner. The waiting item is emitted (keyed `w:pending`) at the end
of the render plan while a generation is busy but the current assistant turn has
no content yet, and the first real card replaces it through `diff_update`.
`KnightRiderSpinner` is a view-only bidirectional "Knight Rider"
scanner: a row of block cells whose brightest cell sweeps right, holds, sweeps
left, then holds, leaving a fading alpha trail. It advances a precomputed frame
index on a 40 ms `Timer`, derives each cell's glyph and colour from the frame,
and takes `baseColor` from the hosting card's `accentColor` (magenta for tool
cards, blue for thinking, amber for response). The body `TextEdit` uses
`Theme.colors.mdText` for markdown kinds (`thinking`/`response`) and
`Theme.colors.textPrimary` otherwise, and opens clicked links with
`Qt.openUrlExternally`. `ChatPanel.qml` binds each delegate
from the `ChatListModel` roles (`kind`, `title`, `body_html`, `token_text`,
`mode`, `is_pending`, `tool_name`, `sections`, `is_delta`, `msg_index`).

`CardBase` carries two header actions driven by `msgIndex` (the source message
index, `-1` for derived cards): a delete icon on every message card
(`fa-trash` `U+F1F8`) removes the turn containing that card, and a reload icon
(`fa-refresh` `U+F021`) on user cards regenerates from that message. Both are
rendered by the shared `CardActionIcon.qml` component (`src/qml/components/`) as
a monospace glyph with the project's hover/colour contract and emit
`deleteRequested` / `regenerateRequested`, which the panel delegates forward to
[`ChatController`](qt-chat-controller.md). The glyphs are Font Awesome
codepoints supplied by the bundled **Sarasa Fixed TC Nerd Font** (registered by
[`app._register_fonts`](app.md) and named by `Theme.fontMono`); the Nerd Font is a
superset of the plain Sarasa Fixed TC, so ordinary text is unchanged. The
header's collapse `MouseArea` is declared before the row so the icons sit on top
and consume their clicks; `actionsEnabled` (bound to the panel's busy flag) makes
them inert while a generation runs.

The collapsible body height in `CardBase.qml` is only animated when the user
clicks the header (`bodyHost.animateBody` gates the `Behavior`); creation and
streaming-driven height growth apply instantly, so they do not churn the scroll
position.

### Body caret navigation

The body `TextEdit` is always keyboard-selectable — there is no separate caret
mode. Because it is `readOnly`, Qt would default `selectByKeyboard` to `false`,
so `CardBase.qml` forces `selectByKeyboard: true`, giving caret movement and
selection with arrows, `Shift`+arrows, `Ctrl`+arrows, `Home`/`End` and `Ctrl+A`
(the browser-style interactions users expect). It is focusable by keyboard
(`activeFocusOnTab: true`) and by click, keeps its highlight when focus leaves
(`persistentSelection: true`), and shows the caret while focused
(`cursorVisible: activeFocus`); `selectionColor` / `selectedTextColor` come from
`Theme.colors.selectionBg` / `selectionFg`. Selection is confined to one card —
the caret does not cross into the neighbouring card's editor.

`TextEdit` never scrolls its parent, so `CardBase` exposes `scrollTarget` (the
hosting `Flickable`, bound by the panel) and emits `caretMoved(contentY, height)`
from `onCursorRectangleChanged` while focused (the caret rectangle is mapped into
the flickable's `contentItem`). `ChatPanel.qml` and `EditorChatPanel.qml` connect
`caretMoved` to a `chatList.ensureVisible(y, h)` helper that nudges `contentY`
only when the caret would be clipped, keeping the caret on screen. That
`contentY` change flows through the existing `onContentYChanged` handler, so
moving the caret away from the bottom deactivates auto-scroll exactly like a
manual scroll would.

The chat list in `ChatPanel.qml` is a **non-virtualized** `Flickable` + `Column` +
`Repeater`: every card is instantiated so `contentHeight` is exact. A virtualized
`ListView` was tried and abandoned — with these variable-height cards its
`contentHeight` is only an estimate, and `positionViewAtEnd()` against that
estimate shifted `originY` without bound (runaway scrolling, a jumping scrollbar,
and a middle-of-viewport landing); a second attempt (ListView + per-delegate
layer caching) rendered blank panels on flick, so it was reverted too.
Auto-scroll sets `contentY = contentHeight - height` through a 30 ms debounce
`Timer` guarded by `!moving && !flicking`, following the newest card whenever
`autoScrollToggle.checked` is true. That flag is the single source of truth:
`onContentYChanged` compares `contentY` against `Math.max(0, contentHeight -
height)` and, on reaching the bottom, calls `activateWithFade()` (button fades
in over 500 ms); scrolling away calls `deactivateWithFade()` (fades out over
500 ms). The toggle starts `checked` so the first streamed card follows, and
clicking it pauses/resumes follow manually (a paused toggle stays visible while
hovered and fades out otherwise). `boundsBehavior: Flickable.StopAtBounds`
prevents dragging past the last card.

Mouse-wheel scrolling is handled by a `WheelHandler` on the chat `Flickable`,
because Qt exposes no wheel-step property and the native platform step is much
smaller: high-resolution or trackpad `pixelDelta` is applied verbatim, while
discrete notches step by `Theme.metrics.wheelScrollStep` (120 px). Unlike a
naive offset, the handler **clamps** the new `contentY` to
`[0, contentHeight - height]` instead of calling `returnToBounds()`, so it never
overshoots the true bounds and cannot show blank space beyond the first/last
card. Wheeling up moves `contentY` away from the bottom, which the
`onContentYChanged` handler observes to deactivate auto-scroll; wheeling back to
the end reactivates it. A vertical `ScrollBar` (`ScrollBar.AsNeeded`) provides
feedback and drag-scroll.

Because the list is not virtualized, **older cards are built collapsed** to bound
scroll cost. `ChatController._COLLAPSE_OLDER_THAN` (12) marks every message older
than the last 12 as collapsed; `CardBase`'s body `TextEdit` uses
`visible: hasBody && !bodyCollapsed`, so Qt never lays out or renders the rich
text of a collapsed body. The card stays in the list as its header, and clicking
the header expands it. Collapsed cards carry a `:c` key suffix so a message
ageing out of the window is rebuilt once (rather than reusing an expanded cached
item). This keeps the per-frame cost proportional to the recent messages, not
the whole history, without touching the exact scroll physics.

## Card types

| Card | `kind` | QML delegate | Border | Header | Body |
|---|---|---|---|---|---|
| User | `user` | `UserCard.qml` | 3px green | `❯` + "User" | escaped `<pre>` |
| Waiting | `waiting` | `WaitingCard.qml` | top/bottom grey | none (headerless) | `KnightRiderSpinner` (pending) |
| Thinking | `thinking` | `ThinkingCard.qml` | top/bottom blue | `◌` + "Thinking" | escaped `<pre>` (streamed while pending) |
| Response | `response` | `ResponseCard.qml` | 3px amber | `◆` + "Response" | `render_markdown` (streamed while pending) |
| Tool call | `tool_call` | `ToolCallCard.qml` | top/bottom magenta | `⚙` + "Tool Call" + mode badge | `highlight_yaml_html` |
| Tool result | `tool_result` | `ToolResultCard.qml` | top/bottom magenta | `▤` + "Tool Result" (subtitle = tool name) | escaped `<pre>` |
| Context banner | `context_banner` | `ContextBanner.qml` | neutral / orange delta | title + section count | structured sections (JSON) |

Tool-call cards carry `mode` (allow/ask/block) and `tool_name`; result cards
carry `tool_name` and `tool_call_id`. Pending result cards set `tool_call_id` so
`ChatListModel.find_pending_result` can locate and replace the card.

## Body HTML generation

1. **User / tool result / thinking** — `_plain_body` normalises CR/CRLF
   newlines to LF, escapes the text with `html.escape`, and wraps it in
   `<pre style="white-space:pre-wrap;margin:0;font-family:Sarasa Fixed TC Nerd Font;line-height:125%">`
   (the `font-family` keeps Qt's `<pre>` from substituting its system monospace
   font, matching `Theme.fontMono`; `line-height` comes from
   `Theme.LINE_HEIGHT_BODY` so plain text matches markdown leading). The LF
   normalisation is required because Qt's rich-text `<pre>` renders each `\r`
   as an extra line break, which would double-space Windows tool output.
   `thinking_body` is a named wrapper over `_plain_body`: thinking streams
   verbatim and deliberately skips the Markdown parser/pygments, since
   re-rendering the full accumulated reasoning on every stream tick was a
   dominant cost.
2. **Response** — `render_markdown` returns sanitized, inline-styled HTML for a
   QML `TextEdit.RichText` (terminal-style colours, CSS bordered tables,
   clickable links, in-memory LaTeX math images; see
   [`qt-markdown`](qt-markdown.md) and [`qt-latex`](qt-latex.md)). During streaming the
   controller uses [`IncrementalMarkdown`](qt-markdown.md#incremental-streaming-renderer-incrementalmarkdown),
   which re-renders only the trailing block.
3. **Tool call** — `_to_yaml_string` serializes `{name, mode, arguments}` and
   `highlight_yaml_html` colourises it into a `<pre>` HTML block.

## Function Reference

### Item construction

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `make_item(kind, *, title="", body_html="", token_text="", collapsed=False, is_pending=False, mode="", tool_name="", tool_call_id="", sections="", is_delta=False, msg_index=-1) -> dict[int, object]` | `kind` — `KIND_*`; `title`/`body_html`/`token_text` — header and body; `collapsed`/`is_pending` — defaults; `mode`/`tool_name`/`tool_call_id`/`sections`/`is_delta` — tool and banner fields; `msg_index` — source message index | role-keyed dict (`int(ChatRole.*)` → value) | Maps every argument onto its `ChatRole` key | None |
| `_card_item(kind, *, title, body_html="", token_count=0, is_pending=False, mode="", tool_name="", tool_call_id="", collapsed=False, msg_index=-1) -> dict[int, object]` | Card fields with a raw `token_count`; `msg_index` | role-keyed dict | Calls `make_item` with `token_text=_token_text(token_count)` | None |
| `_token_text(token_count: int) -> str` | `token_count` | `"42 tk"` | f-string format | None |
| `_plain_body(text: str) -> str` | `text` | escaped `<pre>` block | Normalise CR/CRLF → LF, then `html.escape` into `<pre style="white-space:pre-wrap;margin:0;font-family:…;line-height:125%">` | None |
| `thinking_body(text: str) -> str` | `text` — raw thinking | escaped `<pre>` block | Named wrapper over `_plain_body`; thinking never runs Markdown | None |

### Item builders

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `build_user_item(text: str, *, collapsed=False, msg_index=-1) -> dict[int, object]` | `text`; `collapsed`; `msg_index` | role-keyed dict | `_card_item(KIND_USER, title="User", body_html=_plain_body(text))` | None |
| `build_waiting_item() -> dict[int, object]` | — | role-keyed dict | `make_item(KIND_WAITING, is_pending=True)` — empty title/token/body | None |
| `build_thinking_item(text: str, *, token_count=0, collapsed=False, msg_index=-1) -> dict[int, object]` | `text`; `token_count`; `collapsed`; `msg_index` | role-keyed dict | Body = `thinking_body(text)` (escaped plain text), title "Thinking" | None |
| `build_thinking_pending_item(text="", *, token_count=0, msg_index=-1) -> dict[int, object]` | `text` — partial streamed content; `token_count`; `msg_index` | role-keyed dict | Body = `thinking_body(text)`, title "Thinking", `is_pending=True` | None |
| `build_response_item(text: str, *, token_count=0, collapsed=False, msg_index=-1) -> dict[int, object]` | `text`; `token_count`; `collapsed`; `msg_index` | role-keyed dict | Body = `render_markdown(text)`, title "Response" | None |
| `build_response_pending_item(text="", *, token_count=0, msg_index=-1) -> dict[int, object]` | `text` — partial streamed content; `token_count`; `msg_index` | role-keyed dict | Body = `render_markdown(text)`, title "Response", `is_pending=True` | None |
| `build_tool_call_item(entry: dict, *, token_count=0, collapsed=False, msg_index=-1) -> dict[int, object]` | `entry` — `{name, mode, arguments}`; `collapsed`; `msg_index` | role-keyed dict | `_to_yaml_string` → `highlight_yaml_html`; stores `mode` + `tool_name` | None |
| `build_tool_call_pending_item(name: str, mode: str, token_count=0, msg_index=-1) -> dict[int, object]` | `name`; `mode`; `token_count`; `msg_index` | role-keyed dict | `is_pending=True`, keeps `mode`/`tool_name` | None |
| `build_tool_result_item(name: str, content: str, *, token_count=0, collapsed=False, msg_index=-1) -> dict[int, object]` | `name`; `content`; `token_count`; `collapsed`; `msg_index` | role-keyed dict | Body = `_plain_body(content)`, stores `tool_name` | None |
| `build_tool_result_pending_item(name: str, tool_call_id="", token_count=0) -> dict[int, object]` | `name`; `tool_call_id`; `token_count` | role-keyed dict | `is_pending=True`, stores `tool_call_id` for later swap; no `msg_index` (result message not yet created) | None |

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
