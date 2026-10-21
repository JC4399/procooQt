# qt.context_banner — context banner items & section formatters

Source: `src/qt/context_banner.py`

## Purpose

Build context banner items (initial system context and config deltas) for
`ChatListModel`, rendered by `src/qml/cards/ContextBanner.qml`. Banners are derived UI
items only — `chat.messages` remains canonical. Builders return plain
`ChatRole`-keyed dictionaries and never touch QML objects.

## Deliverables

- `build_context_banner_item` — `KIND_CONTEXT_BANNER` item carrying JSON sections.
- `build_context_sections_from_snapshot` — the full system prompt section only.
- `build_delta_context_sections` — added skills/tools and tool-mode changes.
- Shared section helpers: `_shorten`, `_normalize_sections`.

## Steps / Flow

### Banner item

1. `build_context_banner_item` calls `_normalize_sections` to flatten every
   section's content into a `list[str]` (list-of-lines entries are joined with
   `"\n"`).
2. `make_item(KIND_CONTEXT_BANNER, title=…, sections=json.dumps(normalized),
   collapsed=not is_delta, is_delta=…)` returns the role-keyed dict. The initial
   (non-delta) banner starts collapsed; delta banners start expanded.
3. `ContextBanner.qml` parses `sectionsJson`, picks the neutral or orange delta
   scheme from `isDelta`, seeds `bodyCollapsed` from the `collapsed` role, and
   animates the collapsible body height only when the user toggles the header.
   Creation and content-driven height changes are not animated, so a deferred
   `ChatPanel` auto-scroll never chases a moving height.

### Initial context (snapshot)

`build_context_sections_from_snapshot` emits the System Prompt section only, in
full (untruncated, fenced); no other snapshot fields are rendered.

### Config delta

`build_delta_context_sections` emits Added Activated Skills, Added Tools, and
Tool Mode Changes — each only when non-empty. The
`SkillController` appends the resulting banner and pops any previous trailing
delta so at most one delta is shown.

## Function Reference

### Banner and section builders

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `build_context_banner_item(title: str, sections: list[dict], *, is_delta=False) -> dict[int, object]` | `title` — headline; `sections` — `{header, content}` dicts (content = list of str or list of lists); `is_delta` — orange scheme | role-keyed dict with kind `context_banner` | `_normalize_sections` → `json.dumps` into `sections` role → `make_item` with `collapsed=not is_delta` | None |
| `build_context_sections_from_snapshot(snapshot: dict) -> list[dict]` | `snapshot` — stored context snapshot | list of `{header, content}` dicts | Reads `system_prompt` only; emits the full (untruncated) fenced System Prompt section when non-empty | None |
| `build_delta_context_sections(added_activated: list[dict], added_tools: list[dict], mode_changes: dict[str, tuple[str, str]]) -> list[dict]` | Added skill/tool content dicts; `mode_changes` — tool → `(old, new)` | list of `{header, content}` dicts | Builds "Added Activated Skills", "Added Tools", "Tool Mode Changes" sections, only when non-empty; sorts mode changes | None |

### Shared helpers

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_shorten(text: str, limit: int) -> str` | `text`; `limit` | original or `text[:limit] + "..."` | Length check | None |
| `_normalize_sections(sections: list[dict]) -> list[dict]` | raw `{header, content}` dicts | `{header: str, content: list[str]}` | Joins list-of-line parts with `"\n"` so QML renders a flat list | None |

## Related

- [`qt-chat-items`](qt-chat-items.md) — provides `make_item`, `KIND_CONTEXT_BANNER`, and `ChatRole`.
- [`qt-skill-controller`](qt-skill-controller.md) — appends the delta banner during config sync.
