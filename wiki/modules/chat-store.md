# chat.store — ChatStore

Source: `src/chat/store.py`

## Purpose

JSON-backed CRUD store for chat files and session records. Each chat is a single
JSON file under `storage/chats/`; sessions (names + split layout) live in
`storage/sessions.json`; a lightweight summary index lives in
`storage/chat_index.json`; disk-backed multimodal media lives under
`storage/media/<chat_id>/`. `DEFAULT_SESSION_NAME = "Default"` is created on first
run.

Related: [`chat-media`](chat-media.md), [`chat-worker`](chat-worker.md).

## Deliverables

- Chat persistence: `save_chat`, `load_chat`, `load_all_chats`, `list_chats`,
  `list_chat_ids`, `delete_chat`.
- Chat summary index: `load_summaries` plus the private rebuild/reconcile/update
  helpers, so the sidebar does not parse every full chat file.
- Media cleanup: `delete_chat` / `delete_session` remove the chat's
  `storage/media/<chat_id>/` folder.
- Session management: `list_sessions`, `list_session_records`, `get_session`,
  `get_session_by_id`, `session_id_for`, `get_layout`, `set_layout`,
  `create_session`, `ensure_default_session`, `delete_session`,
  `set_chat_session`.
- Stable per-session UUID `id`, backfilled for legacy records by `_ensure_session_ids`.
- `DEFAULT_SESSION_NAME` module constant.

## Chat file shape

```json
{
  "id": "20240101_120000",
  "skills_config": {"activated": [], "tools": {}},
  "messages": [],
  "session": "Default",
  "created_at": "...",
  "updated_at": "...",
  "message_count": 0,
  "model_name": "qwen3.8-27b",
  "true_input_tokens": 0,
  "true_output_cum": 0,
  "context_snapshot": {...}
}
```

`model_name` records the LLM selected for the chat; when absent the config
default is used. `true_input_tokens` / `true_output_cum` cache the last true API
token counts so the token bar survives a restart; they are written by the live
chat's [`ChatWorker`](chat-worker.md) (`_do_persist`) and restored on hydration.

## `sessions.json` shape

```json
{
  "sessions": [
    {
      "id": "0f6c2e...",
      "name": "Default",
      "created_at": "...",
      "layout": {"splits": [{"chat_ids": ["20240101_120000"], "active_chat_id": "20240101_120000"}]}
    }
  ]
}
```

The `id` is a stable UUID used as the external identity of a session (e.g. by
the control server and the Obsidian plugin). Records written before this field
existed are backfilled in `ChatStore.__init__` via `_ensure_session_ids`.

## `chat_index.json` shape

```json
{
  "chats": [
    {
      "id": "20240101_120000",
      "session": "Default",
      "skills": [],
      "created_at": "...",
      "updated_at": "...",
      "message_count": 12,
      "model_name": "qwen3.8-27b",
      "true_input_tokens": 1234,
      "true_output_cum": 5678,
      "title": "first user message...",
      "has_messages": true,
      "activated_count": 2,
      "allow_count": 3,
      "ask_count": 1,
      "block_count": 0
    }
  ]
}
```

`save_chat` updates the entry for its chat; `delete_chat` / `delete_session`
remove entries. `load_summaries` rebuilds the index from the chat files when it
is missing and reconciles it against the `chats/` directory when present, so
externally added or removed chats are still picked up.

## Function Reference

### `ChatStore.__init__`

| | |
|---|---|
| Signature | `def __init__(self, storage_dir: str) -> None` |
| Inputs | `storage_dir` — root storage path (`chats/` subdir used). |
| Output | `None` |
| Side effects | creates `chats/` dir; points `_sessions_path` at `sessions.json`; points `_index_path` at `chat_index.json`; sets `media_dir` to `storage/media`; creates session/index locks; backfills session ids via `_ensure_session_ids`. |

### `save_chat`

| | |
|---|---|
| Signature | `def save_chat(self, chat_id: str, data: dict) -> None` |
| Output | `None` |
| Side effects | sets `updated_at`, writes `<id>.json` (indent 2) **atomically** (`<id>.json.tmp` + `replace`), so a concurrent worker-thread reader never sees a partial file; updates the chat's `chat_index.json` entry. |

### `load_chat`

| | |
|---|---|
| Signature | `def load_chat(self, chat_id: str) -> dict \| None` |
| Output | chat dict, or `None`. |

### `load_all_chats`

| | |
|---|---|
| Signature | `def load_all_chats(self) -> list[dict]` |
| Output | full parsed chat dicts, each carrying an `"id"` key (filename stem), newest first. |
| Side effects | logs corrupt files, skips them. |

### `list_chats`

| | |
|---|---|
| Signature | `def list_chats(self) -> list[dict]` |
| Output | summary dicts from `load_summaries()` (index rows), newest first. |

### `load_summaries`

| | |
|---|---|
| Signature | `def load_summaries(self) -> list[dict]` |
| Output | lightweight summary rows (`id`, `session`, `skills`, timestamps, `message_count`, `model_name`, token counts, `title`, `has_messages`, skill/tool counts), newest first. |
| Side effects | loads `chat_index.json`; rebuilds it from chat files when missing; reconciles it against `chats/*.json` when present. |

### `list_chat_ids`

| | |
|---|---|
| Signature | `def list_chat_ids(self) -> list[str]` |
| Output | chat id strings (filename stems), newest first; no JSON parsing. |

### `delete_chat`

| | |
|---|---|
| Signature | `def delete_chat(self, chat_id: str) -> None` |
| Output | `None` (safe if missing). |
| Side effects | removes `<id>.json`, `storage/media/<id>/`, and the index entry. |

### Session methods

| Function | Signature | Purpose |
|---|---|---|
| `_default_layout` | `@staticmethod () -> dict` | `{"splits":[{"chat_ids":[],"active_chat_id":""}]}` |
| `list_sessions` | `() -> list[str]` | sorted session names |
| `list_session_records` | `() -> list[dict]` | full records (name, created_at, layout) |
| `get_session` | `(name: str) -> dict \| None` | one session record |
| `get_session_by_id` | `(session_id: str) -> dict \| None` | session record by stable UUID |
| `session_id_for` | `(name: str) -> str` | stable UUID for a session name, or `""` |
| `get_layout` | `(name: str) -> dict` | stored layout or the default |
| `set_layout` | `(name: str, layout: dict) -> None` | persist a session's layout; the load-modify-write runs under the store lock |
| `create_session` | `(name: str, layout: dict \| None = None, session_id: str \| None = None) -> str` | raises `ValueError` on duplicate; returns the session UUID; the check + append run under the store lock |
| `ensure_default_session` | `() -> str` | create `Default` if none; return first session name |
| `delete_session` | `(name: str) -> list[str]` | delete session **and its chats**; return deleted chat ids |
| `set_chat_session` | `(chat_id: str, session_name: str \| None) -> None` | assign/clear a chat's session |

### Private

| Function | Signature | Purpose |
|---|---|---|
| `_load_sessions` | `() -> list[dict]` | read `sessions.json` under the store lock |
| `_save_sessions` | `(sessions: list[dict]) -> None` | write `sessions.json` **atomically** (`.tmp` + `replace`) under the store lock |
| `_ensure_session_ids` | `() -> None` | backfill + persist a UUID `id` on legacy session records |

The store is a single shared instance across every window, so all session-file
mutations run under `_sessions_lock` (a re-entrant `threading.RLock`).
`_save_sessions` writes a temp file and `replace`s it, so a reader on another
thread (e.g. a debounced off-thread `set_layout`, see
[`qt-session-controller`](qt-session-controller.md)) never sees a torn file.
