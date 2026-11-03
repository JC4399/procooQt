# qt.context_banner — context banner items & section formatters

Source: `src/qt/context_banner.py`

## Purpose

Build context banner items (initial system context and skill updates) for
`ChatListModel`, rendered by `src/qml/cards/ContextBanner.qml`. Banners are derived UI
items only — `chat.messages` remains canonical. Builders return plain
`ChatRole`-keyed dictionaries and never touch QML objects.

## Deliverables

- `build_context_banner_item` — `KIND_CONTEXT_BANNER` item carrying JSON sections.
- `build_system_prompt_section` — the shared fenced `System Prompt` section used
  by both the initial context card and the skill-update card.
- `build_context_sections_from_snapshot` — the full system prompt section only.
- `build_skill_update_sections` — the exact pending system-message text.
- Shared section helper: `_normalize_sections`.

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

### Skill update

`build_skill_update_sections` emits the exact pending system-message text using
the same fenced `System Prompt` section as the initial card. The
`ChatWorker` creates the banner when a skill is added, removes it when the
selection is reversed, and commits it when the message is sent. Tool-mode
changes produce no text, so they never create a banner.

## Function Reference

### Banner and section builders

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `build_context_banner_item(title: str, sections: list[dict], *, is_delta=False) -> dict[int, object]` | `title` — headline; `sections` — `{header, content}` dicts (content = list of str or list of lists); `is_delta` — orange scheme | role-keyed dict with kind `context_banner` | `_normalize_sections` → `json.dumps` into `sections` role → `make_item` with `collapsed=not is_delta` | None |
| `build_system_prompt_section(text: str) -> list[dict]` | `text` — exact system-message text | list with one fenced `System Prompt` section, or `[]` when empty | Wraps the text in a fenced block | None |
| `build_context_sections_from_snapshot(snapshot: dict) -> list[dict]` | `snapshot` — stored context snapshot | list of `{header, content}` dicts | Reads `system_prompt` only; delegates to `build_system_prompt_section` | None |
| `build_skill_update_sections(pending_text: str) -> list[dict]` | `pending_text` — exact pending system-message text | list of `{header, content}` dicts | Delegates to `build_system_prompt_section` | None |

### Shared helpers

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `_normalize_sections(sections: list[dict]) -> list[dict]` | raw `{header, content}` dicts | `{header: str, content: list[str]}` | Joins list-of-line parts with `"\n"` so QML renders a flat list | None |

## Related

- [`qt-chat-items`](qt-chat-items.md) — provides `make_item`, `KIND_CONTEXT_BANNER`, and `ChatRole`.
- [`chat-worker`](chat-worker.md) — owns the pending/committed skill-update banner lifecycle.
- [`qt-skill-controller`](qt-skill-controller.md) — pushes config changes to the worker.
