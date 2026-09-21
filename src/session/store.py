"""JSON-backed CRUD store for chat session data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time

logger = logging.getLogger("procoo_qt")


class SessionStore:
    """Persists session metadata and message history as individual JSON files.

    Attributes:
        sessions_dir: ``Path`` to the directory where session JSON files are stored.
    """

    def __init__(self, storage_dir: str) -> None:
        """Create (if needed) the sessions storage directory.

        Args:
            storage_dir: Root storage path; a ``sessions/`` subdirectory will be used.
        """
        self.storage_dir = Path(storage_dir)
        self.sessions_dir = self.storage_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._folders_path = self.storage_dir / "folders.json"

    def save_session(self, session_id: str, data: dict) -> None:
        """Persist a session dictionary to disk, updating its timestamp.

        The write is atomic (temp file + replace) so a concurrent reader on a
        worker thread never sees a partially written file.

        Args:
            session_id: Unique session identifier (used as the JSON filename).
            data: Session data dictionary.
        """
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        path = self.sessions_dir / f"{session_id}.json"
        tmp = path.parent / (path.name + ".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)

    def load_session(self, session_id: str) -> dict | None:
        """Load a previously saved session.

        Args:
            session_id: Session identifier.

        Returns:
            The session dictionary, or ``None`` if not found.
        """
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def load_all_sessions(self) -> list[dict]:
        """Return the full parsed data for all saved sessions, newest first.

        Parses each session JSON exactly once, so callers that need message
        content (derived titles, statuses) do not re-read the files.

        Returns:
            A list of full session dicts, each carrying an ``"id"`` key set to the
            filename stem.
        """
        sessions = []
        for f in sorted(self.sessions_dir.glob("*.json"), key=lambda p: p.name, reverse=True):
            try:
                with open(f) as fh:
                    data = json.load(fh)
            except Exception as e:
                logger.error("Corrupt session file %s: %s", f.name, e)
                continue
            data["id"] = f.stem
            sessions.append(data)
        return sessions

    def list_session_ids(self) -> list[str]:
        """Return all saved session ids, newest first, without parsing any JSON.

        Returns:
            A list of session id strings.
        """
        paths = sorted(self.sessions_dir.glob("*.json"), key=lambda p: p.name, reverse=True)
        return [p.stem for p in paths]

    def list_sessions(self) -> list[dict]:
        """Return summary metadata for all saved sessions, newest first."""
        return [
            {
                "id": data.get("id", ""),
                "folder": data.get("folder"),
                "skills": data.get("skills", []),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": data.get("message_count", 0),
            }
            for data in self.load_all_sessions()
        ]

    def delete_session(self, session_id: str) -> None:
        """Remove a session file from disk if it exists.

        Args:
            session_id: Session identifier to delete.
        """
        path = self.sessions_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()

    # ------------------------------------------------------------------
    #  Folder storage
    # ------------------------------------------------------------------

    def _load_folders(self) -> list[dict]:
        if not self._folders_path.exists():
            return []
        try:
            with open(self._folders_path) as f:
                data = json.load(f)
            return data.get("folders", [])
        except Exception:
            return []

    def _save_folders(self, folders: list[dict]) -> None:
        with open(self._folders_path, "w") as f:
            json.dump({"folders": folders}, f, indent=2)

    def list_folders(self) -> list[str]:
        return sorted([f["name"] for f in self._load_folders()])

    def create_folder(self, name: str) -> None:
        folders = self._load_folders()
        if any(f["name"] == name for f in folders):
            raise ValueError(f"Folder '{name}' already exists.")
        folders.append(
            {
                "name": name,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self._save_folders(folders)

    def delete_folder(self, name: str) -> list[str]:
        """Delete a folder and unlink all sessions in it. Returns affected session IDs."""
        folders = self._load_folders()
        if not any(f["name"] == name for f in folders):
            raise ValueError(f"Folder '{name}' not found.")
        folders = [f for f in folders if f["name"] != name]
        self._save_folders(folders)

        affected = []
        for fpath in self.sessions_dir.glob("*.json"):
            with open(fpath) as fh:
                data = json.load(fh)
            if data.get("folder") == name:
                data["folder"] = None
                data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with open(fpath, "w") as fh:
                    json.dump(data, fh, indent=2, default=str)
                affected.append(fpath.stem)
        return affected

    def set_session_folder(self, session_id: str, folder_name: str | None) -> None:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            raise ValueError(f"Session '{session_id}' not found.")
        with open(path) as f:
            data = json.load(f)
        data["folder"] = folder_name
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
