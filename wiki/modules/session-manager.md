# session.manager — SessionManager

Source: `procooQt/src/session/manager.py`

## Purpose

Factory and registry for `Agent` objects keyed by session ID. A module-level
singleton `session_manager` is shared across the app.

## Deliverables

- `session_manager` singleton.
- `create_session`, `get_session`, `update_session_config`,
  `remove_session`, `cleanup_idle_sessions`.

## Function Reference

### `SessionManager.__init__`

| | |
|---|---|
| Signature | `def __init__(self) -> None` |
| Output | `None` (empty `sessions: dict[str, Agent]`). |

### `create_session`

| | |
|---|---|
| Signature | `async def create_session(self, session_id, model=None, primary_skill_contents=None, secondary_skill_contents=None, tool_functions=None, tool_config=None, skills_dir="", system_message="You are a helpful assistant.", sampling_config=None, initial_messages=None, summary_prompt="", session_limits=None) -> Agent` |
| Inputs | mirrors `Agent.__init__` args. |
| Output | newly created `Agent`. |
| Flow | if `session_id` exists, `remove_session` first → construct `Agent` → register. |

### `get_session`

| | |
|---|---|
| Signature | `def get_session(self, session_id: str) -> Agent \| None` |
| Output | live session or `None`. |

### `update_session_config`

| | |
|---|---|
| Signature | `def update_session_config(self, session_id, primary_skill_contents, secondary_skill_contents, tool_functions, tool_config) -> dict` |
| Output | `Agent.update_skill_config` result (or `{"warnings": []}` if no session). |

### `remove_session`

| | |
|---|---|
| Signature | `def remove_session(self, session_id: str) -> None` |
| Output | `None` (safe if missing). |

### `cleanup_idle_sessions`

| | |
|---|---|
| Signature | `async def cleanup_idle_sessions(self, max_idle_minutes: int = 30) -> None` |
| Notes | placeholder (`pass`) for future idle cleanup. |
