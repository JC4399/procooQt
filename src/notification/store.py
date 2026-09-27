"""JSON-backed persistence for notification history."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("procoo_qt")


class NotificationStore:
    """Reads and writes the notification list as a single JSON file.

    Attributes:
        path: Path to ``notifications.json``.
    """

    def __init__(self, storage_dir: str) -> None:
        """Initialise the store.

        Args:
            storage_dir: Root storage directory; the file lives directly in it.
        """
        self.path = Path(storage_dir) / "notifications.json"

    # ------------------------------------------------------------------
    #  Public: CRUD
    # ------------------------------------------------------------------

    def load(self) -> list[dict]:
        """Load stored notification dicts.

        Returns:
            A list of raw notification dicts (empty when missing or corrupt).
        """
        if not self.path.is_file():
            return []
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as error:
            logger.error("Failed to read notifications: %s", error)
            return []
        items = data.get("notifications", []) if isinstance(data, dict) else []
        return items if isinstance(items, list) else []

    def save(self, notifications: list[dict]) -> None:
        """Atomically persist the full notification list.

        Args:
            notifications: Notification dicts, newest first.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.parent / (self.path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"notifications": notifications}, f, indent=2, default=str)
            tmp.replace(self.path)
        except OSError as error:
            logger.error("Failed to write notifications: %s", error)
