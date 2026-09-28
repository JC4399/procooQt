# Configuration (overview)

## Purpose

`ConfigManager` (`src/config/manager.py`) loads application configuration
from a YAML file and exposes validated accessors for paths, chat limits, and
the LLM model. Missing keys raise `ConfigError` so the app fails fast at
startup.

Full function reference: [`modules/config-manager`](modules/config-manager.md).

## Config schema (`config/config.yaml`)

```yaml
server:
  host: "127.0.0.1"          # event server bind (localhost by default)
  port: 12840

paths:
  # Relative to the procooQt project root (resolved against _PROJECT_ROOT in app.py).
  capabilities_dir: "../capabilities"   # holds skills/ and automations/
  # skills_dir / automations_dir are derived from capabilities_dir but can be overridden.
  storage_dir: "./storage"   # sessions.json + chats/ + automations.json + notifications.json

auth:
  api_keys: []               # event-server API keys (empty disables auth)

limits:
  max_chat_mb: 70            # 0 or negative disables the byte-size limit
  max_chat_tokens: 0         # 0 or negative disables the token limit

agent:
  system_prompt: "You are a helpful assistant."
  summary_prompt: |
    The current chat is running too long. ... Always include the full path
    of working folders, working files, and other important files ...

llm:
  - model_name: "qwen3.8-27b"
    api_key: "ollama"
    api_base: "http://localhost:3333/v1"
    default: true
```

`config/config.yaml` is gitignored; `config/config_template.yaml` is committed
and holds the same keys with placeholder values.

### Relative paths

`ConfigManager` returns the raw string from YAML. `ProcooApp._resolve` turns
any relative path absolute against `_PROJECT_ROOT` = the `procooQt/` directory
(the parent of `src/`):

| Config value | Resolves to |
|---|---|
| `capabilities_dir: "../capabilities"` | `<repo-root>/capabilities` |
| `skills_dir` (derived) | `<capabilities_dir>/skills` |
| `automations_dir` (derived) | `<capabilities_dir>/automations` |
| `storage_dir: "./storage"` | `<procooQt>/storage` |

Absolute paths are used as-is. An explicit `paths.skills_dir` or
`paths.automations_dir` overrides the derived value. The resolved `skills_dir`
also seeds the `_presets/` subdirectory used by `PresetStore`. `ChatStore` uses
`storage/sessions.json` for session records/layout and `storage/chats/` for
chat files; `AutomationManager` uses `storage/automations.json` and
`NotificationManager` uses `storage/notifications.json`.

### Event server (`server`) and `auth`

`server.host` / `server.port` configure the automation event HTTP server
([`automation-server`](modules/automation-server.md)); it binds `127.0.0.1` by
default. `auth.api_keys` is a list of accepted keys; when non-empty, requests to
`POST /event/{name}` must present a matching `Authorization: Bearer <key>` or
`X-Api-Key` header. An empty list disables authentication.

### Chat limits (`limits`)

When a chat's message history exceeds `max_chat_mb` (converted to bytes via
`chat_max_bytes`) or its token count exceeds `max_chat_tokens`, the agent
summarizes the chat and starts a new one. Setting either value to `0` or any
negative number (e.g. `-1`) disables that limit. When a key is absent, the
manager falls back to `70` MB and `150000` tokens respectively; the committed
config sets `max_chat_tokens: 0` to disable the token limit.

### Agent prompts (`agent`)

- `system_prompt` — base system prompt for every agent.
- `summary_prompt` — instruction sent to the LLM when summarizing an
  over-limit chat.

### LLM (`llm`)

A non-empty list of model entries. Exactly one entry must have `default: true`;
that entry is the default model for new chats and must provide `model_name`,
`api_key`, and `api_base`. Every entry's `model_name` is offered in the per-chat
model selector (the `SkillDock` dropdown), and `llm_config(model_name)` resolves
any entry on demand. `auth.api_keys` is exposed by `ConfigManager.api_keys` and
used by the event server (see above).

## Loading flow

1. `ProcooApp` constructs `ConfigManager(str(_PROJECT_ROOT / "config"))`.
2. `_load_file` resolves `config_dir/config.yaml`, falling back to the
   project-root `config/config.yaml`; raise `ConfigError` if neither exists.
3. `yaml.safe_load` into `self._data`.
4. `_default_llm` validates: `llm` is a non-empty list, and exactly one entry
   has `default: true` (zero or more than one raises `ConfigError`).
5. Accessors lazily pull nested values via `_get` (required) or
   `_get_optional` (with defaults); `_get_llm_key` fetches a required key from
   the default entry and `llm_config(model_name)` from any named entry.

## Startup wiring (`src/app.py`)

```python
backend = ProcooApp(str(_PROJECT_ROOT / "config"))
```

`ProcooApp.__init__` builds `ConfigManager`, resolves `capabilities_dir` /
`skills_dir` / `storage_dir`, and then constructs `SkillManager`, `ChatStore`,
`PresetStore`, `AutomationManager`, and `NotificationManager` from the config.
`main()` logs the active `api_base` and `model`, and if construction raises
`ProcooError` it logs the critical detail and exits.

Once the QML engine has loaded, `ProcooQtUI.start()` runs the controller
startup that depends on config: `SessionController.start()` emits validation
toasts, ensures a `Default` session exists, and rebuilds/opens the workspace
panels; `SkillController.start()` begins watching the skills directory;
`EditorController.start()` builds the file tree; `AutomationController.start()`
starts the automation watcher, the cron scheduler, and the event server.
