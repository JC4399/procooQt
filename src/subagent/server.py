"""Sub-agent HTTP server — local bridge from tool scripts to headless agents.

Tool scripts are subprocesses and cannot access the in-process chat manager, so
they call this small aiohttp server instead.  It binds localhost by default and
reuses the same API-key scheme as the automation and control servers.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import TYPE_CHECKING

from aiohttp import web
from pydantic import ValidationError

from ..util.error.types import SubAgentError
from .models import SubAgentSpec

if TYPE_CHECKING:
    from .manager import SubAgentManager

logger = logging.getLogger("procoo_qt")


class SubAgentServer:
    """HTTP server exposing the run and health endpoints."""

    def __init__(
        self,
        host: str,
        port: int,
        api_keys: list[str],
        manager: SubAgentManager,
    ) -> None:
        """Initialise the server.

        Args:
            host: Interface to bind (e.g. ``"127.0.0.1"``).
            port: TCP port to listen on.
            api_keys: Accepted API keys; an empty list disables authentication.
            manager: The manager that runs sub-agents.
        """
        self._host = host
        self._port = port
        self._api_keys = list(api_keys)
        self._manager = manager
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
        logger.info("Sub-agent server stopped")

    # ------------------------------------------------------------------
    #  Private: Startup
    # ------------------------------------------------------------------

    async def _start(self) -> None:
        """Create the aiohttp application and bind the TCP site."""
        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_post("/subagents/run", self._handle_run)
        app_runner = web.AppRunner(app)
        await app_runner.setup()
        site = web.TCPSite(app_runner, self._host, self._port)
        await site.start()
        self._app_runner = app_runner
        auth = "api-key" if self._api_keys else "open"
        logger.info(
            "Sub-agent server listening on http://%s:%s (%s)",
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
            logger.error("Sub-agent server failed to start: %s", error)

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

    async def _handle_run(self, request: web.Request) -> web.Response:
        """Run one sub-agent and block until it finishes.

        Args:
            request: A ``POST /subagents/run`` request carrying a spec body.

        Returns:
            ``{"text", "error", "log_path"}``, or a 4xx error.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        payload = await self._read_payload(request)
        if payload is None:
            return web.json_response({"error": "invalid JSON body"}, status=400)
        try:
            spec = SubAgentSpec(**payload)
            record = await self._manager.run(spec)
        except (ValidationError, TypeError) as error:
            return self._validation_error(error)
        except SubAgentError as error:
            return self._subagent_error(error)
        return web.json_response(
            {
                "text": record.text,
                "error": record.error,
                "log_path": record.log_path,
            }
        )

    # ------------------------------------------------------------------
    #  Private: Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validation_error(error: ValidationError | TypeError) -> web.Response:
        """Build a 400 response for an invalid spec.

        Args:
            error: The pydantic validation error or request-shape error.

        Returns:
            A JSON error response.
        """
        return web.json_response({"error": str(error)}, status=400)

    @staticmethod
    def _subagent_error(error: SubAgentError) -> web.Response:
        """Build a 400 response for a rejected sub-agent request.

        Args:
            error: The manager error.

        Returns:
            A JSON error response.
        """
        return web.json_response(
            {"error": error.brief, "detail": error.detail},
            status=400,
        )

    # ------------------------------------------------------------------
    #  Private: Request helpers
    # ------------------------------------------------------------------

    async def _read_payload(self, request: web.Request) -> dict | None:
        """Read an optional JSON object body from the request.

        Args:
            request: The incoming request.

        Returns:
            A payload dict (empty when no body), or ``None`` when the body is
            present but not a JSON object.
        """
        if not request.can_read_body:
            return {}
        try:
            data = await request.json()
        except Exception:
            return None
        if isinstance(data, dict):
            return data
        return None

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
