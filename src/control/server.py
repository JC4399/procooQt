"""Control HTTP server — external session/window control for tools (e.g. Obsidian).

External programs call this server to create, open, and delete Procoo sessions
and their windows. It is intentionally small and separate from the automation
event server so the two can be configured and bound independently. The server
runs on the qasync event loop and therefore shares the app's single loop with
the UI, so handlers may call the :class:`WindowManager` directly.

Requests must present a matching key via ``Authorization: Bearer <key>`` or the
``X-Api-Key`` header when keys are configured; an empty key list disables
authentication. The server binds ``127.0.0.1`` by default.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web

if TYPE_CHECKING:
    from ..chat.store import ChatStore
    from ..qt.window_manager import WindowManager

logger = logging.getLogger("procoo_qt")

#: Maximum length of a session name accepted from the control API.
MAX_NAME_LEN = 60

#: Fallback session name when a request supplies neither a usable name nor an id.
DEFAULT_SESSION_NAME = "Procoo session"


class ControlServer:
    """HTTP server exposing session/window create, open, and delete endpoints."""

    def __init__(
        self,
        host: str,
        port: int,
        api_keys: list[str],
        chat_store: ChatStore,
        windows: WindowManager,
    ) -> None:
        """Initialise the control server.

        Args:
            host: Interface to bind (e.g. ``"127.0.0.1"``).
            port: TCP port to listen on.
            api_keys: Accepted API keys; an empty list disables authentication.
            chat_store: Resolves session ids to names.
            windows: Opens, focuses, and closes session windows.
        """
        self._host = host
        self._port = port
        self._api_keys = list(api_keys)
        self._chat_store = chat_store
        self._windows = windows
        self._app_runner: web.AppRunner | None = None
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    #  Public: Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Schedule the server startup on the running event loop."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.ensure_future(self._start())
        self._task.add_done_callback(self._on_start_done)

    async def stop(self) -> None:
        """Shut the HTTP server down and release the socket."""
        if self._app_runner is not None:
            await self._app_runner.cleanup()
            self._app_runner = None
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        logger.info("Control server stopped")

    # ------------------------------------------------------------------
    #  Private: Startup
    # ------------------------------------------------------------------

    async def _start(self) -> None:
        """Create the aiohttp application and bind the TCP site."""
        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_post("/sessions", self._handle_create_session)
        app.router.add_post("/sessions/open", self._handle_open_session)
        app.router.add_post("/sessions/delete", self._handle_delete_session)
        app_runner = web.AppRunner(app)
        await app_runner.setup()
        site = web.TCPSite(app_runner, self._host, self._port)
        await site.start()
        self._app_runner = app_runner
        auth = "api-key" if self._api_keys else "open"
        logger.info(
            "Control server listening on http://%s:%s (%s)",
            self._host,
            self._port,
            auth,
        )

    def _on_start_done(self, task: asyncio.Task[None]) -> None:
        """Log an unexpected server startup failure.

        Args:
            task: The completed startup task.
        """
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("Control server failed to start: %s", error)

    # ------------------------------------------------------------------
    #  Private: Handlers
    # ------------------------------------------------------------------

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Return a simple liveness response.

        Args:
            request: The incoming request (unused).

        Returns:
            A JSON ``{"status": "ok"}`` response.
        """
        return web.json_response({"status": "ok"})

    async def _handle_create_session(self, request: web.Request) -> web.Response:
        """Create a session (if needed) and open it in a window.

        Args:
            request: A ``POST /sessions`` request with ``{id?, name?}``.

        Returns:
            ``{id, name, created, open}``, or a 4xx error response.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        payload = await self._read_payload(request)
        if payload is None:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        session_id = str(payload.get("id", "") or "")
        name = self._sanitize_name(payload.get("name"))

        existing = self._chat_store.get_session_by_id(session_id) if session_id else None
        if existing is not None:
            opened = self._windows.open_session(str(existing["name"]))
            return web.json_response(
                {
                    "id": existing.get("id", ""),
                    "name": existing["name"],
                    "created": False,
                    "open": opened,
                }
            )

        name_match = self._chat_store.get_session(name)
        if name_match is not None:
            opened = self._windows.open_session(name)
            return web.json_response(
                {
                    "id": name_match.get("id", ""),
                    "name": name,
                    "created": False,
                    "open": opened,
                }
            )

        new_id = self._windows.create_session(name, session_id=session_id)
        if not new_id:
            return web.json_response({"error": "failed to create session"}, status=500)
        record = self._chat_store.get_session_by_id(new_id)
        return web.json_response(
            {
                "id": new_id,
                "name": record["name"] if record else name,
                "created": True,
                "open": True,
            }
        )

    async def _handle_open_session(self, request: web.Request) -> web.Response:
        """Open (or focus) the window for a session.

        Args:
            request: A ``POST /sessions/open`` request with ``{id?, name?}``.

        Returns:
            ``{id, name, open}`` or a 404 error response.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        payload = await self._read_payload(request)
        if payload is None:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        record = self._resolve_session(payload)
        if record is None:
            return web.json_response({"error": "session not found"}, status=404)
        opened = self._windows.open_session(str(record["name"]))
        return web.json_response(
            {"id": record.get("id", ""), "name": record["name"], "open": opened}
        )

    async def _handle_delete_session(self, request: web.Request) -> web.Response:
        """Delete a session, its chats, and its window.

        Args:
            request: A ``POST /sessions/delete`` request with ``{id?, name?}``.

        Returns:
            ``{id, name, deleted}`` or a 404 error response.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        payload = await self._read_payload(request)
        if payload is None:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        record = self._resolve_session(payload)
        if record is None:
            return web.json_response({"error": "session not found"}, status=404)
        deleted = self._windows.delete_session(str(record["name"]))
        return web.json_response(
            {"id": record.get("id", ""), "name": record["name"], "deleted": deleted}
        )

    # ------------------------------------------------------------------
    #  Private: Request helpers
    # ------------------------------------------------------------------

    def _resolve_session(self, payload: dict[str, Any]) -> dict | None:
        """Resolve a session record from an ``id`` or ``name`` payload field.

        Args:
            payload: The parsed request body.

        Returns:
            The session record, or ``None`` when neither field matches.
        """
        session_id = str(payload.get("id", "") or "")
        if session_id:
            record = self._chat_store.get_session_by_id(session_id)
            if record is not None:
                return record
        name = str(payload.get("name", "") or "").strip()
        if name:
            return self._chat_store.get_session(name)
        return None

    @staticmethod
    def _sanitize_name(value: Any) -> str:
        """Normalise a requested session name.

        Collapses whitespace, trims, and truncates to :data:`MAX_NAME_LEN`.

        Args:
            value: The raw ``name`` field.

        Returns:
            A usable session name, or :data:`DEFAULT_SESSION_NAME`.
        """
        text = " ".join(str(value or "").split())
        if not text:
            return DEFAULT_SESSION_NAME
        return text[:MAX_NAME_LEN]

    async def _read_payload(self, request: web.Request) -> dict | None:
        """Read an optional JSON object body from the request.

        Args:
            request: The incoming request.

        Returns:
            A payload dict (empty when no body), or ``None`` when the body is
            present but not valid JSON.
        """
        if not request.can_read_body:
            return {}
        try:
            data = await request.json()
        except Exception:
            return None
        if isinstance(data, dict):
            return data
        return {"data": data}

    def _authorized(self, request: web.Request) -> bool:
        """Return whether the request carries an accepted API key.

        Args:
            request: The incoming request.

        Returns:
            ``True`` when authentication is disabled or the key matches.
        """
        if not self._api_keys:
            return True
        return self._extract_key(request) in self._api_keys

    @staticmethod
    def _extract_key(request: web.Request) -> str:
        """Extract the API key from the Authorization or ``X-Api-Key`` header.

        Args:
            request: The incoming request.

        Returns:
            The presented key, or an empty string.
        """
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[len("bearer ") :].strip()
        return request.headers.get("X-Api-Key", "").strip()
