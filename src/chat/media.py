"""Disk-backed media store for multimodal chat images.

Images arrive from tools and sub-agents as base64 ``data:`` URLs. Keeping those
strings in ``Agent.messages`` makes the conversation history large and forces
every persistence write to re-serialize them. This store writes the decoded
bytes once under ``storage/media/<chat_id>/`` and replaces the message content
with a compact ``procoo-media://`` reference. The reference is expanded back to
a data URL only when a prompt is sent to the LLM.
"""

from __future__ import annotations

import base64
from collections import OrderedDict
import hashlib
import logging
from pathlib import Path
import re
import threading
from typing import Any

logger = logging.getLogger("procoo_qt")

_SCHEME = "procoo-media://"
_DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.DOTALL)
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]")

_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "application/pdf": "pdf",
}
_MIME_BY_EXT = {f".{ext}": mime for mime, ext in _EXTENSIONS.items()}


def safe_media_name(value: str) -> str:
    """Return a filesystem-safe folder name for a chat id.

    Args:
        value: The chat id.

    Returns:
        A name containing only letters, digits, dots, dashes, and underscores.
    """
    return _SAFE_NAME_RE.sub("_", value) or "chat"


class MediaStore:
    """Persist multimodal media on disk and expand references for LLM calls.

    Attributes:
        media_dir: Root directory holding per-chat media folders.
    """

    def __init__(self, media_dir: str, *, memo_limit: int = 8) -> None:
        """Initialise the store and ensure its root directory exists.

        Args:
            media_dir: Root directory for per-chat media folders.
            memo_limit: Maximum number of expanded data URLs kept in memory.
        """
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._memo: OrderedDict[str, str] = OrderedDict()
        self._memo_limit = memo_limit
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    #  Public: store / resolve
    # ------------------------------------------------------------------

    def store_data_url(self, chat_id: str, url: str) -> str:
        """Persist a base64 data URL and return its compact reference.

        Non-data URLs are returned unchanged, so existing remote image URLs keep
        working.

        Args:
            chat_id: Chat that owns the media.
            url: A ``data:<mime>;base64,...`` URL.

        Returns:
            A ``procoo-media://<chat>/<file>`` reference, or ``url`` when it is
            not a base64 data URL.
        """
        match = _DATA_URL_RE.match(url)
        if match is None:
            return url
        mime = match.group("mime").lower()
        try:
            raw = base64.b64decode(match.group("data"))
        except Exception:
            logger.warning("MediaStore could not decode a %s payload", mime)
            return url
        folder = self.media_dir / self._safe_name(chat_id)
        folder.mkdir(parents=True, exist_ok=True)
        digest = hashlib.blake2b(raw, digest_size=16).hexdigest()
        extension = _EXTENSIONS.get(mime, "bin")
        path = folder / f"{digest}.{extension}"
        if not path.exists():
            path.write_bytes(raw)
        return f"{_SCHEME}{folder.name}/{path.name}"

    def resolve(self, url: str) -> str:
        """Expand a media reference back to a base64 data URL.

        Args:
            url: A ``procoo-media://`` reference or any other URL.

        Returns:
            The original URL when it is not a media reference or the file is
            missing, otherwise a ``data:`` URL.
        """
        if not url.startswith(_SCHEME):
            return url
        with self._lock:
            cached = self._memo.get(url)
            if cached is not None:
                self._memo.move_to_end(url)
                return cached
        path = self._resolve_path(url)
        if path is None:
            logger.warning("MediaStore missing media reference: %s", url)
            return url
        try:
            raw = path.read_bytes()
        except OSError as error:
            logger.warning("MediaStore failed to read %s: %s", path, error)
            return url
        mime = _MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
        data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        with self._lock:
            self._memo[url] = data_url
            self._memo.move_to_end(url)
            while len(self._memo) > self._memo_limit:
                self._memo.popitem(last=False)
        return data_url

    def expand_message(self, value: Any) -> Any:
        """Expand media references in a copied message tree in place.

        Args:
            value: A message dict, list, or scalar already copied by the caller.

        Returns:
            The same value with ``image_url`` references expanded.
        """
        if isinstance(value, dict):
            if value.get("type") == "image_url":
                inner = value.get("image_url")
                if isinstance(inner, dict):
                    url = inner.get("url", "")
                    resolved = self.resolve(url) if isinstance(url, str) else url
                    if resolved != url:
                        inner["url"] = resolved
            for item in value.values():
                self.expand_message(item)
        elif isinstance(value, list):
            for item in value:
                self.expand_message(item)
        return value

    # ------------------------------------------------------------------
    #  Private
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_name(value: str) -> str:
        """Return a filesystem-safe folder name for a chat id."""
        return safe_media_name(value)

    def _resolve_path(self, url: str) -> Path | None:
        """Resolve a media reference to a file inside :attr:`media_dir`."""
        relative = url[len(_SCHEME) :]
        try:
            path = (self.media_dir / relative).resolve()
            root = self.media_dir.resolve()
        except OSError:
            return None
        if not path.is_relative_to(root):
            return None
        return path
