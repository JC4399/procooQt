# config.manager — ConfigManager

Source: `procooQt/src/config/manager.py`

## Purpose

Reads configuration from a YAML file and exposes validated, read-only
properties. Raises `ConfigError` on missing keys (fail-fast at startup).

## Deliverables

- Parsed `self._data` dict from `config.yaml`.
- Properties: `skills_dir`, `storage_dir`, `session_max_mb`,
  `session_max_bytes`, `session_max_tokens`, `agent_system_prompt`,
  `agent_summary_prompt`, `llm_model_name`, `llm_api_key`, `llm_api_base`.
- `ConfigError` with `brief` + `detail` on missing/invalid config.

See also: [Configuration overview](../02-Configuration.md).

## Function Reference

### `ConfigManager.__init__`

| | |
|---|---|
| Signature | `def __init__(self, config_dir: str = "./config") -> None` |
| Inputs | `config_dir` (`str`) — directory containing `config.yaml`. |
| Output | `None` |
| Flow | store dir → `_load_file()` → `_enabled_llm()`. |

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

### `ConfigManager._enabled_llm`

| | |
|---|---|
| Signature | `def _enabled_llm(self) -> dict` |
| Output | the single enabled LLM entry dict. |
| Raises | `ConfigError` if `llm` is missing/empty/not a list, no entry enabled, or >1 enabled. |

### `ConfigManager._get_llm_key`

| | |
|---|---|
| Signature | `def _get_llm_key(self, key: str) -> str` |
| Inputs | `key` (`str`) — entry key to fetch. |
| Output | value of `key` in the enabled LLM entry. |
| Raises | `ConfigError` if key missing from the enabled entry. |

### Properties

| Property | Returns | Notes |
|---|---|---|
| `skills_dir` | `str` | `_get("paths", "skills_dir")` |
| `storage_dir` | `str` | `_get("paths", "storage_dir")` |
| `session_max_mb` | `int` | `_get_optional("limits", "max_session_mb", default=70)` |
| `session_max_bytes` | `int` | `session_max_mb * 1024 * 1024` |
| `session_max_tokens` | `int` | `_get_optional("limits", "max_session_tokens", default=150000)` |
| `agent_system_prompt` | `str` | `_get_optional("agent", "system_prompt", default=...)` |
| `agent_summary_prompt` | `str` | `_get_optional("agent", "summary_prompt", default=...)` |
| `llm_model_name` | `str` | enabled LLM `model_name` |
| `llm_api_key` | `str` | enabled LLM `api_key` |
| `llm_api_base` | `str` | enabled LLM `api_base` |
