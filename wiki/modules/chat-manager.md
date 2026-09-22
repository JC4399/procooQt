# chat.manager — ChatManager

Source: `src/chat/manager.py`

## Purpose

Factory and registry for `Agent` objects keyed by chat ID. A module-level
singleton `chat_manager` is shared across the app.

## Deliverables

- `chat_manager` singleton.
- `create_chat`, `get_chat`, `update_chat_config`, `remove_chat`,
  `cleanup_idle_chats`.

## Function Reference

### `ChatManager.__init__`

| | |
|---|---|
| Signature | `def __init__(self) -> None` |
| Output | `None` (empty `chats: dict[str, Agent]`). |

### `create_chat`

| | |
|---|---|
| Signature | `def create_chat(self, chat_id, model=None, primary_skill_contents=None, secondary_skill_contents=None, tool_functions=None, tool_config=None, skills_dir="", system_message="You are a helpful assistant.", sampling_config=None, initial_messages=None, summary_prompt="", chat_limits=None) -> Agent` |
| Inputs | mirrors `Agent.__init__` args. |
| Output | newly created `Agent`. |
| Flow | if `chat_id` exists, `remove_chat` first → construct `Agent` → register. Synchronous (no awaits); callers that must not block the UI run it via `asyncio.to_thread`. |

### `get_chat`

| | |
|---|---|
| Signature | `def get_chat(self, chat_id: str) -> Agent \| None` |
| Output | live chat or `None`. |

### `update_chat_config`

| | |
|---|---|
| Signature | `def update_chat_config(self, chat_id, primary_skill_contents, secondary_skill_contents, tool_functions, tool_config) -> dict` |
| Output | `Agent.update_skill_config` result (or `{"warnings": []}` if no chat). |

### `remove_chat`

| | |
|---|---|
| Signature | `def remove_chat(self, chat_id: str) -> None` |
| Output | `None` (safe if missing). |

### `cleanup_idle_chats`

| | |
|---|---|
| Signature | `async def cleanup_idle_chats(self, max_idle_minutes: int = 30) -> None` |
| Notes | placeholder (`pass`) for future idle cleanup. |
