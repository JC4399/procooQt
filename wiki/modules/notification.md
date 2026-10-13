# notification — models, store, manager

Sources: `procooQt/src/notification/models.py`, `src/notification/store.py`,
`src/notification/manager.py`

## Purpose

Stores and tracks automation run results so the user can see what ran. Each
successful run becomes a **log** notification, an informational result becomes
**info**, and a failure becomes **error**. Success logs are auto-acknowledged
when the notification page opens; info and error stay unread until the user
confirms them. The package is Qt-free — the
[notification controller](qt-notification-controller.md) calls it and emits the
UI signals.

## Deliverables

- `NotificationKind` (`log` / `info` / `error`) and `NotificationItem`.
- `NotificationStore` — atomic read/write of `storage/notifications.json`.
- `NotificationManager` — in-memory list (newest first), unread counts, read
  marking, paged/searchable history; persists on every mutation.

## Mapping

| `AutomationResultKind` | `NotificationKind` |
|---|---|
| `success` | `log` |
| `info` | `info` |
| `error` | `error` |

## Steps / Flow

- `add(result)` → build a `NotificationItem` (new `uuid` id, `read=False`),
  insert at the front, persist.
- `mark_logs_read()` → set every unread `log` to read; returns the ids that
  changed (drives the page-open behaviour).
- `mark_read(id)` → acknowledge one item (Confirm).
- `history(offset, limit, search)` / `total(search)` → paged, case-insensitive
  filter over task + message for the history window.

## Function Reference

### `NotificationManager`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, storage_dir: str) -> None` | storage dir | `None` | load persisted items | — |
| `def add(self, result: AutomationResult) -> NotificationItem` | result | new item | map kind → insert front → persist | Writes `notifications.json` |
| `def get(self, item_id: str) -> NotificationItem \| None` | id | item or `None` | linear scan | — |
| `def unread_counts(self) -> dict[NotificationKind, int]` | — | per-kind counts (zeros included) | iterate unread | — |
| `def mark_logs_read(self) -> list[str]` | — | ids marked read | mark unread logs read | Persists when changed |
| `def mark_read(self, item_id: str) -> bool` | id | changed? | mark one read | Persists when changed |
| `def history(self, *, offset=0, limit=20, search="") -> list[NotificationItem]` | paging + search | page | `_filter` → slice | — |
| `def total(self, search: str = "") -> int` | search | match count | `len(_filter(...))` | — |

### `NotificationStore`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, storage_dir: str) -> None` | storage dir | `None` | set `path` | — |
| `def load(self) -> list[dict]` | — | raw dicts | read JSON; empty on missing/corrupt | Logs read errors |
| `def save(self, notifications: list[dict]) -> None` | items, newest first | `None` | temp file + replace | Logs write errors |

### `NotificationItem`

`id`, `kind`, `task`, `path`, `message`, `log`, `data`, `timestamp`, `read`.

## See also

- [automation-runner](automation-runner.md) — produces `AutomationResult`.
- [qt-notification-controller](qt-notification-controller.md) — UI + read semantics.
- [notification-lifecycle-flow](../flows/notification-lifecycle-flow.md) — end-to-end.
