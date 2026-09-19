"""JSON-backed CRUD store for skill/tool configuration presets."""

from __future__ import annotations

import json
from pathlib import Path


class PresetStore:
    """Persists preset configurations as individual JSON files on disk.

    Attributes:
        presets_dir: ``Path`` to the directory where preset JSON files are stored.
    """

    def __init__(self, presets_dir: str) -> None:
        """Create (if needed) the presets storage directory.

        Args:
            presets_dir: Filesystem path to the presets directory.
        """
        self.presets_dir = Path(presets_dir)
        self.presets_dir.mkdir(parents=True, exist_ok=True)

    def list_presets(self) -> list[str]:
        """Return the names of all saved presets (sorted alphabetically)."""
        names = []
        for f in sorted(self.presets_dir.glob("*.json")):
            names.append(f.stem)
        return names

    def load_preset(self, name: str) -> dict | None:
        """Load a preset's configuration from disk.

        Args:
            name: Preset name (without ``.json`` extension).

        Returns:
            The preset dictionary, or ``None`` if the file does not exist.
        """
        path = self.presets_dir / f"{name}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    #  Mutate
    # ------------------------------------------------------------------

    def save_preset(self, name: str, config: dict) -> None:
        """Save (or overwrite) a preset configuration to disk.

        Args:
            name: Preset name.
            config: Dictionary of preset settings (``name`` key will be injected).
        """
        config["name"] = name
        path = self.presets_dir / f"{name}.json"
        with open(path, "w") as f:
            json.dump(config, f, indent=2, default=str)

    def delete_preset(self, name: str) -> None:
        """Delete a preset file if it exists.

        Args:
            name: Preset name to delete.
        """
        path = self.presets_dir / f"{name}.json"
        if path.exists():
            path.unlink()
