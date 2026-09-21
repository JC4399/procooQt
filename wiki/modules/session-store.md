# session.store — SessionStore

Source: `procooQt/src/session/store.py`

## Purpose

JSON-backed CRUD store for chat session data and session folders. Each session
is a single JSON file under `storage/sessions/`; folders live in
`storage/folders.json`.

## Deliverables

- Session persistence: `save_session`, `load_session`, `list_sessions`,
  `load_all_sessions`, `list_session_ids`, `delete_session`.
- Folder management: `list_folders`, `create_folder`, `delete_folder`,
  `set_session_folder`.

## Session file shape

```json
{
  "id": "20240101_120000",
  "skills_config": {"primary": [], "secondary": [], "tools": {}},
  "messages": [],
  "folder": null,
  "created_at": "...",
  "updated_at": "...",
  "message_count": 0,
  "context_snapshot": {...}
}
```

## Function Reference

### `SessionStore.__init__`

| | |
|---|---|
| Signature | `def __init__(self, storage_dir: str) -> None` |
| Inputs | `storage_dir` — root storage path (`sessions/` subdir used). |
| Output | `None` |
| Side effects | creates `sessions/` dir. |

### `save_session`

| | |
|---|---|
| Signature | `def save_session(self, session_id: str, data: dict) -> None` |
| Inputs | `session_id` — used as filename; `data` — session dict. |
| Output | `None` |
| Side effects | sets `updated_at`, writes `<id>.json` (indent 2) **atomically** (`<id>.json.tmp` + `replace`), so a concurrent worker-thread reader never sees a partial file. |

### `load_session`

| | |
|---|---|
| Signature | `def load_session(self, session_id: str) -> dict \| None` |
| Output | session dict, or `None`. |

### `list_sessions`

| | |
|---|---|
| Signature | `def list_sessions(self) -> list[dict]` |
| Output | summary dicts (`id`, `folder`, `skills`, `created_at`, `updated_at`, `message_count`), newest first. |
| Flow | thin projection over `load_all_sessions` (each file parsed once). |
| Side effects | logs corrupt files, skips them. |

### `load_all_sessions`

| | |
|---|---|
| Signature | `def load_all_sessions(self) -> list[dict]` |
| Output | full parsed session dicts, each carrying an `"id"` key (filename stem), newest first. |
| Flow | globs `*.json`, `json.load` once per file. |
| Side effects | logs corrupt files, skips them. |

### `list_session_ids`

| | |
|---|---|
| Signature | `def list_session_ids(self) -> list[str]` |
| Output | session id strings (filename stems), newest first. |
| Flow | globs `*.json` only — no JSON parsing. |

### `delete_session`

| | |
|---|---|
| Signature | `def delete_session(self, session_id: str) -> None` |
| Output | `None` |

### Folder methods

| Function | Signature | Purpose |
|---|---|---|
| `list_folders` | `() -> list[str]` | sorted folder names |
| `create_folder` | `(name: str) -> None` | raises `ValueError` on duplicate |
| `delete_folder` | `(name: str) -> list[str]` | unlink sessions, return affected ids |
| `set_session_folder` | `(session_id: str, folder_name: str \| None) -> None` | assign/clear folder |

### Private

| Function | Signature | Purpose |
|---|---|---|
| `_load_folders` | `() -> list[dict]` | read `folders.json` |
| `_save_folders` | `(folders: list[dict]) -> None` | write `folders.json` |
