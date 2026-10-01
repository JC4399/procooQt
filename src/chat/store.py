"""JSON-backed CRUD store for chat data and session groups."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
import uuid

logger = logging.getLogger("procoo_qt")

DEFAULT_SESSION_NAME = "Default"


class ChatStore:
    """Persists chat metadata and message history as individual JSON files.

    Attributes:
        chats_dir: ``Path`` to the directory where chat JSON files are stored.
    """

    def __init__(self, storage_dir: str) -> None:
        """Create (if needed) the chats storage directory.

        Args:
            storage_dir: Root storage path; a ``chats/`` subdirectory will be used.
        """
        self.storage_dir = Path(storage_dir)
        self.chats_dir = self.storage_dir / "chats"
        self.chats_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_path = self.storage_dir / "sessions.json"
        self._ensure_session_ids()

    def save_chat(self, chat_id: str, data: dict) -> None:
        """Persist a chat dictionary to disk, updating its timestamp.

        The write is atomic (temp file + replace) so a concurrent reader on a
        worker thread never sees a partially written file.

        Args:
            chat_id: Unique chat identifier (used as the JSON filename).
            data: Chat data dictionary.
        """
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        path = self.chats_dir / f"{chat_id}.json"
        tmp = path.parent / (path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)

    def load_chat(self, chat_id: str) -> dict | None:
        """Load a previously saved chat.

        Args:
            chat_id: Chat identifier.

        Returns:
            The chat dictionary, or ``None`` if not found.
        """
        path = self.chats_dir / f"{chat_id}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_all_chats(self) -> list[dict]:
        """Return the full parsed data for all saved chats, newest first.

        Parses each chat JSON exactly once, so callers that need message
        content (derived titles, statuses) do not re-read the files.

        Returns:
            A list of full chat dicts, each carrying an ``"id"`` key set to the
            filename stem.
        """
        chats = []
        for f in sorted(self.chats_dir.glob("*.json"), key=lambda p: p.name, reverse=True):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception as e:
                logger.error("Corrupt chat file %s: %s", f.name, e)
                continue
            data["id"] = f.stem
            chats.append(data)
        return chats

    def list_chat_ids(self) -> list[str]:
        """Return all saved chat ids, newest first, without parsing any JSON.

        Returns:
            A list of chat id strings.
        """
        paths = sorted(self.chats_dir.glob("*.json"), key=lambda p: p.name, reverse=True)
        return [p.stem for p in paths]

    def list_chats(self) -> list[dict]:
        """Return summary metadata for all saved chats, newest first."""
        return [
            {
                "id": data.get("id", ""),
                "session": data.get("session"),
                "skills": data.get("skills", []),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": data.get("message_count", 0),
            }
            for data in self.load_all_chats()
        ]

    def delete_chat(self, chat_id: str) -> None:
        """Remove a chat file from disk if it exists.

        Args:
            chat_id: Chat identifier to delete.
        """
        path = self.chats_dir / f"{chat_id}.json"
        if path.exists():
            path.unlink()

    # ------------------------------------------------------------------
    #  Session storage
    # ------------------------------------------------------------------

    @staticmethod
    def _default_layout() -> dict:
        """Return the layout for a fresh session with a single empty panel.

        Returns:
            A layout dict ``{"splits": [{"chat_ids": [], "active_chat_id": ""}]}``.
        """
        return {"splits": [{"chat_ids": [], "active_chat_id": ""}]}

    def _load_sessions(self) -> list[dict]:
        if not self._sessions_path.exists():
            return []
        try:
            with open(self._sessions_path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("sessions", [])
        except Exception:
            return []

    def _save_sessions(self, sessions: list[dict]) -> None:
        with open(self._sessions_path, "w", encoding="utf-8") as f:
            json.dump({"sessions": sessions}, f, indent=2)

    def _ensure_session_ids(self) -> None:
        """Backfill a stable UUID ``id`` onto any session record lacking one.

        Existing ``sessions.json`` files predate session ids, so this runs once at
        construction time and persists the generated ids. Records that already
        carry an id are left untouched.
        """
        sessions = self._load_sessions()
        changed = False
        for session in sessions:
            if not session.get("id"):
                session["id"] = uuid.uuid4().hex
                changed = True
        if changed:
            self._save_sessions(sessions)

    def list_sessions(self) -> list[str]:
        return sorted([s["name"] for s in self._load_sessions()])

    def list_session_records(self) -> list[dict]:
        """Return full session records (name, created_at, layout)."""
        return list(self._load_sessions())

    def get_session(self, name: str) -> dict | None:
        """Return the record for a session, or ``None`` if not found."""
        for session in self._load_sessions():
            if session["name"] == name:
                return session
        return None

    def get_session_by_id(self, session_id: str) -> dict | None:
        """Return the record for a session by its stable id, or ``None``.

        Args:
            session_id: The UUID stored in the session record's ``id`` field.

        Returns:
            The session record dict, or ``None`` when no session has that id.
        """
        if not session_id:
            return None
        for session in self._load_sessions():
            if session.get("id") == session_id:
                return session
        return None

    def session_id_for(self, name: str) -> str:
        """Return the stable id of a session by name, or an empty string.

        Args:
            name: The session name.

        Returns:
            The session's UUID, or ``""`` when the session is unknown.
        """
        session = self.get_session(name)
        return str(session.get("id", "")) if session else ""

    def get_layout(self, name: str) -> dict:
        """Return a session's saved split layout, or the default layout."""
        session = self.get_session(name)
        if not session:
            return self._default_layout()
        return session.get("layout") or self._default_layout()

    def set_layout(self, name: str, layout: dict) -> None:
        """Persist a session's split layout.

        Args:
            name: The session name.
            layout: The layout dict to store.
        """
        sessions = self._load_sessions()
        for session in sessions:
            if session["name"] == name:
                session["layout"] = layout
                break
        else:
            return
        self._save_sessions(sessions)

    def create_session(
        self, name: str, layout: dict | None = None, session_id: str | None = None
    ) -> str:
        """Create a session record and return its stable id.

        Args:
            name: The unique, human-readable session name.
            layout: Optional initial split layout; the default layout is used
                when omitted.
            session_id: Optional stable UUID for the session. A new UUID is
                generated when omitted.

        Returns:
            The session's stable UUID.

        Raises:
            ValueError: If a session with *name* already exists.
        """
        sessions = self._load_sessions()
        if any(s["name"] == name for s in sessions):
            raise ValueError(f"Session '{name}' already exists.")
        stable_id = session_id or uuid.uuid4().hex
        sessions.append(
            {
                "id": stable_id,
                "name": name,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "layout": layout or self._default_layout(),
            }
        )
        self._save_sessions(sessions)
        return stable_id

    def ensure_default_session(self) -> str:
        """Create the ``Default`` session if no sessions exist.

        Returns:
            The name of the first session (``Default`` when freshly created).
        """
        sessions = self._load_sessions()
        if not sessions:
            self.create_session(DEFAULT_SESSION_NAME)
            return DEFAULT_SESSION_NAME
        return sessions[0]["name"]

    def delete_session(self, name: str) -> list[str]:
        """Delete a session and its chats. Returns the deleted chat IDs."""
        sessions = self._load_sessions()
        if not any(s["name"] == name for s in sessions):
            raise ValueError(f"Session '{name}' not found.")
        sessions = [s for s in sessions if s["name"] != name]
        self._save_sessions(sessions)

        affected = []
        for fpath in self.chats_dir.glob("*.json"):
            with open(fpath, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("session") == name:
                fpath.unlink()
                affected.append(fpath.stem)
        return affected

    def set_chat_session(self, chat_id: str, session_name: str | None) -> None:
        path = self.chats_dir / f"{chat_id}.json"
        if not path.exists():
            raise ValueError(f"Chat '{chat_id}' not found.")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["session"] = session_name
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
