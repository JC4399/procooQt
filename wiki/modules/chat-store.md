# chat.store — ChatStore

Source: `src/chat/store.py`

## Purpose

JSON-backed CRUD store for chat files and session records. Each chat is a single
JSON file under `storage/chats/`; sessions (names + split layout) live in
`storage/sessions.json`. `DEFAULT_SESSION_NAME = "Default"` is created on first
run.

## Deliverables

- Chat persistence: `save_chat`, `load_chat`, `load_all_chats`, `list_chats`,
  `list_chat_ids`, `delete_chat`.
- Session management: `list_sessions`, `list_session_records`, `get_session`,
  `get_layout`, `set_layout`, `create_session`, `ensure_default_session`,
  `delete_session`, `set_chat_session`.
- `DEFAULT_SESSION_NAME` module constant.

## Chat file shape

```json
{
  "id": "20240101_120000",
  "skills_config": {"primary": [], "secondary": [], "tools": {}},
  "messages": [],
  "session": "Default",
  "created_at": "...",
  "updated_at": "...",
  "message_count": 0,
  "context_snapshot": {...}
}
```

## `sessions.json` shape

```json
{
  "sessions": [
    {
      "name": "Default",
      "created_at": "...",
      "layout": {"splits": [{"chat_ids": ["20240101_120000"], "active_chat_id": "20240101_120000"}]}
    }
  ]
}
```

## Function Reference

### `ChatStore.__init__`

| | |
|---|---|
| Signature | `def __init__(self, storage_dir: str) -> None` |
| Inputs | `storage_dir` — root storage path (`chats/` subdir used). |
| Output | `None` |
| Side effects | creates `chats/` dir; points `_sessions_path` at `sessions.json`. |

### `save_chat`

| | |
|---|---|
| Signature | `def save_chat(self, chat_id: str, data: dict) -> None` |
| Output | `None` |
| Side effects | sets `updated_at`, writes `<id>.json` (indent 2) **atomically** (`<id>.json.tmp` + `replace`), so a concurrent worker-thread reader never sees a partial file. |

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
| Output | summary dicts (`id`, `session`, `skills`, `created_at`, `updated_at`, `message_count`), newest first. |

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

### Session methods

| Function | Signature | Purpose |
|---|---|---|
| `_default_layout` | `@staticmethod () -> dict` | `{"splits":[{"chat_ids":[],"active_chat_id":""}]}` |
| `list_sessions` | `() -> list[str]` | sorted session names |
| `list_session_records` | `() -> list[dict]` | full records (name, created_at, layout) |
| `get_session` | `(name: str) -> dict \| None` | one session record |
| `get_layout` | `(name: str) -> dict` | stored layout or the default |
| `set_layout` | `(name: str, layout: dict) -> None` | persist a session's layout |
| `create_session` | `(name: str, layout: dict \| None = None) -> None` | raises `ValueError` on duplicate |
| `ensure_default_session` | `() -> str` | create `Default` if none; return first session name |
| `delete_session` | `(name: str) -> list[str]` | delete session **and its chats**; return deleted chat ids |
| `set_chat_session` | `(chat_id: str, session_name: str \| None) -> None` | assign/clear a chat's session |

### Private

| Function | Signature | Purpose |
|---|---|---|
| `_load_sessions` | `() -> list[dict]` | read `sessions.json` |
| `_save_sessions` | `(sessions: list[dict]) -> None` | write `sessions.json` |
