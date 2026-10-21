# config.manager — ConfigManager

Source: `procooQt/src/config/manager.py`

## Purpose

Reads configuration from a YAML file and exposes validated, read-only
properties. Raises `ConfigError` on missing keys (fail-fast at startup).

## Deliverables

- Parsed `self._data` dict from `config.yaml`.
- Properties: `capabilities_dir`, `skills_dir`, `automations_dir`,
  `storage_dir`, `server_host`, `server_port`, `api_keys`,
  `control_server_host`, `control_server_port`, `control_server_api_keys`,
  `subagent_enabled`, `subagent_host`, `subagent_port`, `subagent_api_keys`,
  `subagent_default_model`, `subagent_max_concurrent`,
  `subagent_default_timeout`, `subagent_max_timeout`,
  `chat_max_mb`, `chat_max_bytes`, `chat_max_tokens`, `agent_system_prompt`,
  `agent_summary_prompt`, `llm_models`, `llm_model_name`, `llm_api_key`,
  `llm_api_base`.
- Named-model lookup `llm_config(model_name)`.
- `ConfigError` with `brief` + `detail` on missing/invalid config.

See also: [Configuration overview](../02-Configuration.md).

## Function Reference

### `ConfigManager.__init__`

| | |
|---|---|
| Signature | `def __init__(self, config_dir: str = "./config") -> None` |
| Inputs | `config_dir` (`str`) — directory containing `config.yaml`. |
| Output | `None` |
| Flow | store dir → `_load_file()` → `_default_llm()`. |

### `ConfigManager._load_file`

| | |
|---|---|
| Signature | `def _load_file(self) -> None` |
| Output | `None` |
| Flow | resolve path; fall back to `<project_root>/config/config.yaml`; raise if missing; `yaml.safe_load`. |
| Raises | `ConfigError` when no file found. |

### `ConfigManager._get`

| | |
|---|---|
| Signature | `def _get(self, *keys: str) -> Any` |
| Inputs | `*keys` — nested key path. |
| Output | value at the nested path. |
| Raises | `ConfigError` when a key is missing (reports full `" -> "` path). |

### `ConfigManager._get_optional`

| | |
|---|---|
| Signature | `def _get_optional(self, *keys: str, default: Any = None) -> Any` |
| Inputs | `*keys` — nested key path; `default` — value returned when the path is absent. |
| Output | value at the nested path, or `default`. |

### `ConfigManager._default_llm`

| | |
|---|---|
| Signature | `def _default_llm(self) -> dict` |
| Output | the single `default: true` LLM entry dict. |
| Raises | `ConfigError` if `llm` is missing/empty/not a list, no entry default, or >1 default. |

### `ConfigManager.llm_config`

| | |
|---|---|
| Signature | `def llm_config(self, model_name: str) -> dict` |
| Inputs | `model_name` (`str`) — the entry to look up. |
| Output | `{"model_name", "api_key", "api_base"}` for the matching entry. |
| Raises | `ConfigError` if no entry matches, or the entry is missing a required key. |

### `ConfigManager._get_llm_key`

| | |
|---|---|
| Signature | `def _get_llm_key(self, key: str) -> str` |
| Inputs | `key` (`str`) — entry key to fetch. |
| Output | value of `key` in the default LLM entry. |
| Raises | `ConfigError` if key missing from the default entry. |

### Properties

| Property | Returns | Notes |
|---|---|---|
| `capabilities_dir` | `str` | `_get_optional("paths", "capabilities_dir", default="./capabilities")` |
| `skills_dir` | `str` | explicit `paths.skills_dir` or `<capabilities_dir>/skills` |
| `automations_dir` | `str` | explicit `paths.automations_dir` or `<capabilities_dir>/automations` |
| `storage_dir` | `str` | `_get("paths", "storage_dir")` |
| `server_host` | `str` | `_get_optional("server", "host", default="127.0.0.1")` |
| `server_port` | `int` | `_get_optional("server", "port", default=12840)` |
| `api_keys` | `list[str]` | `_get_optional("auth", "api_keys", default=[])` |
| `control_server_host` | `str` | `_get_optional("control_server", "host", default="127.0.0.1")` |
| `control_server_port` | `int` | `_get_optional("control_server", "port", default=12841)` |
| `control_server_api_keys` | `list[str]` | `control_server.api_keys`, falling back to `auth.api_keys` |
| `subagent_enabled` | `bool` | `_get_optional("subagent", "enabled", default=True)` |
| `subagent_host` | `str` | `_get_optional("subagent", "host", default="127.0.0.1")` |
| `subagent_port` | `int` | `_get_optional("subagent", "port", default=12842)` |
| `subagent_api_keys` | `list[str]` | `subagent.api_keys`, falling back to `auth.api_keys` |
| `subagent_default_model` | `str` | `_get_optional("subagent", "default_model", default="")`; empty falls back to the LLM default |
| `subagent_max_concurrent` | `int` | simultaneous runs (default `4`) |
| `subagent_default_timeout` | `int` | per-run seconds (default `900`) |
| `subagent_max_timeout` | `int` | hard timeout cap (default `3600`) |
| `chat_max_mb` | `int` | `_get_optional("limits", "max_chat_mb", default=70)` |
| `chat_max_bytes` | `int` | `chat_max_mb * 1024 * 1024` |
| `chat_max_tokens` | `int` | `_get_optional("limits", "max_chat_tokens", default=150000)` |
| `agent_system_prompt` | `str` | `_get_optional("agent", "system_prompt")`; returns `""` when unset, null, or empty |
| `agent_summary_prompt` | `str` | `_get_optional("agent", "summary_prompt", default=...)` |
| `llm_models` | `list[str]` | `model_name` of every `llm` entry |
| `llm_model_name` | `str` | default LLM `model_name` |
| `llm_api_key` | `str` | default LLM `api_key` |
| `llm_api_base` | `str` | default LLM `api_base` |
