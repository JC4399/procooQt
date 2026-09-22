"""Configuration loader with YAML file support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util.error.types import ConfigError


class ConfigManager:
    """Reads configuration from a YAML file. Raises ConfigError on missing keys."""

    def __init__(self, config_dir: str = "./config") -> None:
        """Load configuration from the given directory."""
        self._data: dict = {}
        self._config_dir = Path(config_dir).resolve()
        self._load_file()
        self._enabled_llm()

    def _load_file(self) -> None:
        config_path = self._config_dir / "config.yaml"
        if not config_path.is_file():
            config_path = Path(__file__).resolve().parents[3] / "config" / "config.yaml"
        if not config_path.is_file():
            raise ConfigError(
                brief="Config file not found",
                detail=f"Config file not found at {self._config_dir / 'config.yaml'}",
            )
        import yaml

        with open(config_path) as f:
            self._data = yaml.safe_load(f) or {}

    def _get(self, *keys: str) -> Any:
        """Retrieve a nested config value, raising ConfigError if missing."""
        current_dict: dict = self._data
        for key in keys:
            if not isinstance(current_dict, dict) or key not in current_dict:
                key_path = " -> ".join(keys)
                raise ConfigError(
                    brief=f"Missing config key: {key}",
                    detail=f"Missing config key: {key_path} (missing '{key}')",
                )
            current_dict = current_dict[key]
        return current_dict

    def _get_optional(self, *keys: str, default: Any = None) -> Any:
        """Retrieve a nested config value, falling back to *default* if missing."""
        current: Any = self._data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    @property
    def skills_dir(self) -> str:
        """Path to the skills directory."""
        return self._get("paths", "skills_dir")

    @property
    def storage_dir(self) -> str:
        """Path to the storage directory."""
        return self._get("paths", "storage_dir")

    # ------------------------------------------------------------------
    #  Chat limits
    # ------------------------------------------------------------------

    @property
    def chat_max_mb(self) -> int:
        """Chat history size limit in megabytes (0 disables the byte limit)."""
        return int(self._get_optional("limits", "max_chat_mb", default=70))

    @property
    def chat_max_bytes(self) -> int:
        """Chat history size limit in bytes, derived from ``chat_max_mb``."""
        return self.chat_max_mb * 1024 * 1024

    @property
    def chat_max_tokens(self) -> int:
        """Chat token limit (0 disables the token limit)."""
        return int(self._get_optional("limits", "max_chat_tokens", default=150000))

    # ------------------------------------------------------------------
    #  Agent prompts
    # ------------------------------------------------------------------

    @property
    def agent_system_prompt(self) -> str:
        """Base system prompt for new agents."""
        default = "You are a helpful assistant."
        return str(self._get_optional("agent", "system_prompt", default=default))

    @property
    def agent_summary_prompt(self) -> str:
        """Instruction sent to the LLM when summarizing an over-limit chat."""
        default = (
            "The current chat is running too long. "
            "You are summarizing the conversation and create a summary for staring a new chat. "
            "Produce a concise but complete summary capturing: "
            "purpose and deliverables for current task, steps and progress, key facts, "
            "and decisions, actions taken with their results, and any open questions or "
            "next steps. The summary must be self-contained so a new conversation can "
            "continue seamlessly from it. Always include the full path of working folders, "
            "working files, and other important files to ensure all important information is "
            "passed down."
        )
        return str(self._get_optional("agent", "summary_prompt", default=default))

    def _enabled_llm(self) -> dict:
        """Return the LLM config entry with ``enable: true``.

        Raises:
            ConfigError: If the ``llm`` section is missing, empty, or not a
                list, if no entry is enabled, or if more than one entry is
                enabled.
        """
        models = self._data.get("llm")
        if not isinstance(models, list) or not models:
            raise ConfigError(
                brief="No LLM models configured",
                detail="Config key 'llm' must be a non-empty list of model entries",
            )
        enabled = [m for m in models if isinstance(m, dict) and m.get("enable") is True]
        if not enabled:
            raise ConfigError(
                brief="No LLM model enabled",
                detail="Set 'enable: true' on exactly one entry under 'llm'",
            )
        if len(enabled) > 1:
            names = ", ".join(m.get("model_name", "?") for m in enabled)
            raise ConfigError(
                brief="Multiple LLM models enabled",
                detail=f"Enabled models: {names} — enable only one",
            )
        return enabled[0]

    @property
    def llm_model_name(self) -> str:
        """Model name of the enabled LLM."""
        return self._get_llm_key("model_name")

    @property
    def llm_api_key(self) -> str:
        """API key of the enabled LLM."""
        return self._get_llm_key("api_key")

    @property
    def llm_api_base(self) -> str:
        """API base URL of the enabled LLM."""
        return self._get_llm_key("api_base")

    def _get_llm_key(self, key: str) -> str:
        """Fetch a required key from the enabled LLM entry, raising ConfigError if missing.

        Args:
            key: The entry key to fetch.

        Raises:
            ConfigError: If the key is missing from the enabled LLM entry.
        """
        model = self._enabled_llm()
        if key not in model:
            name = model.get("model_name", "?")
            raise ConfigError(
                brief=f"Missing LLM config key: {key}",
                detail=f"LLM entry '{name}' is missing required key '{key}'",
            )
        return model[key]
