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
        self._default_llm()

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

        with open(config_path, encoding="utf-8") as f:
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
    def capabilities_dir(self) -> str:
        """Path to the root capabilities directory (holding ``skills/`` and ``automations/``)."""
        return str(self._get_optional("paths", "capabilities_dir", default="./capabilities"))

    @property
    def skills_dir(self) -> str:
        """Path to the skills directory.

        An explicit ``paths.skills_dir`` overrides the default derived from
        :attr:`capabilities_dir`; otherwise ``<capabilities_dir>/skills`` is used.
        """
        explicit = self._get_optional("paths", "skills_dir")
        if explicit:
            return str(explicit)
        return str(Path(self.capabilities_dir) / "skills")

    @property
    def automations_dir(self) -> str:
        """Path to the automations directory.

        An explicit ``paths.automations_dir`` overrides the default derived from
        :attr:`capabilities_dir`; otherwise ``<capabilities_dir>/automations`` is used.
        """
        explicit = self._get_optional("paths", "automations_dir")
        if explicit:
            return str(explicit)
        return str(Path(self.capabilities_dir) / "automations")

    @property
    def storage_dir(self) -> str:
        """Path to the storage directory."""
        return self._get("paths", "storage_dir")

    # ------------------------------------------------------------------
    #  Event server
    # ------------------------------------------------------------------

    @property
    def server_host(self) -> str:
        """Host the event HTTP server binds to (defaults to localhost)."""
        return str(self._get_optional("server", "host", default="127.0.0.1"))

    @property
    def server_port(self) -> int:
        """Port the event HTTP server listens on."""
        return int(self._get_optional("server", "port", default=12840))

    @property
    def api_keys(self) -> list[str]:
        """API keys accepted by the event server (empty disables authentication)."""
        keys = self._get_optional("auth", "api_keys", default=[]) or []
        return [str(key) for key in keys]

    # ------------------------------------------------------------------
    #  Control server
    # ------------------------------------------------------------------

    @property
    def control_server_host(self) -> str:
        """Host the control HTTP server binds to (defaults to localhost)."""
        return str(self._get_optional("control_server", "host", default="127.0.0.1"))

    @property
    def control_server_port(self) -> int:
        """Port the control HTTP server listens on."""
        return int(self._get_optional("control_server", "port", default=12841))

    @property
    def control_server_api_keys(self) -> list[str]:
        """API keys accepted by the control server.

        Falls back to ``auth.api_keys`` when ``control_server.api_keys`` is not
        set, so a single key set can gate both servers. An empty list disables
        authentication.
        """
        keys = self._get_optional("control_server", "api_keys", default=None)
        if keys is None:
            keys = self._get_optional("auth", "api_keys", default=[]) or []
        return [str(key) for key in keys]

    # ------------------------------------------------------------------
    #  Chat limits
    # ------------------------------------------------------------------

    @property
    def chat_max_mb(self) -> int:
        """Chat history size limit in megabytes (0 or negative disables the byte limit)."""
        return int(self._get_optional("limits", "max_chat_mb", default=70))

    @property
    def chat_max_bytes(self) -> int:
        """Chat history size limit in bytes, derived from ``chat_max_mb``."""
        return self.chat_max_mb * 1024 * 1024

    @property
    def chat_max_tokens(self) -> int:
        """Chat token limit (0 or negative disables the token limit)."""
        return int(self._get_optional("limits", "max_chat_tokens", default=150000))

    # ------------------------------------------------------------------
    #  Agent prompts
    # ------------------------------------------------------------------

    @property
    def agent_system_prompt(self) -> str:
        """Base system prompt for new agents (empty string when unset in config)."""
        value = self._get_optional("agent", "system_prompt")
        return "" if value is None else str(value)

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

    def _default_llm(self) -> dict:
        """Return the LLM config entry with ``default: true``.

        Raises:
            ConfigError: If the ``llm`` section is missing, empty, or not a
                list, if no entry is default, or if more than one entry is
                marked as default.
        """
        models = self._data.get("llm")
        if not isinstance(models, list) or not models:
            raise ConfigError(
                brief="No LLM models configured",
                detail="Config key 'llm' must be a non-empty list of model entries",
            )
        default = [m for m in models if isinstance(m, dict) and m.get("default") is True]
        if not default:
            raise ConfigError(
                brief="No default LLM model",
                detail="Set 'default: true' on exactly one entry under 'llm'",
            )
        if len(default) > 1:
            names = ", ".join(m.get("model_name", "?") for m in default)
            raise ConfigError(
                brief="Multiple default LLM models",
                detail=f"Default models: {names} — mark only one as default",
            )
        return default[0]

    @property
    def llm_models(self) -> list[str]:
        """Return the model names of every configured LLM entry."""
        models = self._data.get("llm")
        if not isinstance(models, list) or not models:
            raise ConfigError(
                brief="No LLM models configured",
                detail="Config key 'llm' must be a non-empty list of model entries",
            )
        return [
            str(m.get("model_name", ""))
            for m in models
            if isinstance(m, dict) and m.get("model_name")
        ]

    def llm_config(self, model_name: str) -> dict:
        """Return the connection config for a named LLM entry.

        Args:
            model_name: The ``model_name`` of the entry to look up.

        Returns:
            A ``{"model_name", "api_key", "api_base"}`` dict.

        Raises:
            ConfigError: If no entry matches *model_name*, or the entry is
                missing a required key.
        """
        models = self._data.get("llm")
        if isinstance(models, list):
            for model in models:
                if not isinstance(model, dict) or model.get("model_name") != model_name:
                    continue
                for key in ("model_name", "api_key", "api_base"):
                    if key not in model:
                        raise ConfigError(
                            brief=f"Missing LLM config key: {key}",
                            detail=(f"LLM entry '{model_name}' is missing required key '{key}'"),
                        )
                return {
                    "model_name": model["model_name"],
                    "api_key": model["api_key"],
                    "api_base": model["api_base"],
                }
        raise ConfigError(
            brief=f"Unknown LLM model: {model_name}",
            detail=f"No entry under 'llm' has model_name '{model_name}'",
        )

    @property
    def llm_model_name(self) -> str:
        """Model name of the default LLM."""
        return self._get_llm_key("model_name")

    @property
    def llm_api_key(self) -> str:
        """API key of the default LLM."""
        return self._get_llm_key("api_key")

    @property
    def llm_api_base(self) -> str:
        """API base URL of the default LLM."""
        return self._get_llm_key("api_base")

    def _get_llm_key(self, key: str) -> str:
        """Fetch a required key from the default LLM entry, raising ConfigError if missing.

        Args:
            key: The entry key to fetch.

        Raises:
            ConfigError: If the key is missing from the default LLM entry.
        """
        model = self._default_llm()
        if key not in model:
            name = model.get("model_name", "?")
            raise ConfigError(
                brief=f"Missing LLM config key: {key}",
                detail=f"LLM entry '{name}' is missing required key '{key}'",
            )
        return model[key]
