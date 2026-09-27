"""Automation event server — receives external HTTP events and runs automations.

External programs call ``POST /event/<event-name>`` to trigger every enabled
event-driven automation registered for that name.  The server runs on the
qasync event loop and therefore shares the app's single loop with the scheduler
and UI.  When ``auth.api_keys`` is configured, requests must present a matching
key via ``Authorization: Bearer <key>`` or the ``X-Api-Key`` header.  The server
binds ``127.0.0.1`` by default.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging
from typing import TYPE_CHECKING

from aiohttp import web

from .models import AutomationResult

if TYPE_CHECKING:
    from .manager import AutomationManager
    from .runner import AutomationRunner

logger = logging.getLogger("procoo_qt")


class AutomationEventServer:
    """HTTP server dispatching named events to matching automations."""

    def __init__(
        self,
        host: str,
        port: int,
        api_keys: list[str],
        manager: AutomationManager,
        runner: AutomationRunner,
        on_result: Callable[[AutomationResult], None],
    ) -> None:
        """Initialise the event server.

        Args:
            host: Interface to bind (e.g. ``"127.0.0.1"``).
            port: TCP port to listen on.
            api_keys: Accepted API keys; an empty list disables authentication.
            manager: Provides event-automation lookups and run-state recording.
            runner: Executes automations.
            on_result: Callback invoked with each completed result.
        """
        self._host = host
        self._port = port
        self._api_keys = list(api_keys)
        self._manager = manager
        self._runner = runner
        self._on_result = on_result
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
        logger.info("Automation event server stopped")

    # ------------------------------------------------------------------
    #  Private: Startup
    # ------------------------------------------------------------------

    async def _start(self) -> None:
        """Create the aiohttp application and bind the TCP site."""
        app = web.Application()
        app.router.add_post("/event/{name}", self._handle_event)
        app.router.add_get("/health", self._handle_health)
        app_runner = web.AppRunner(app)
        await app_runner.setup()
        site = web.TCPSite(app_runner, self._host, self._port)
        await site.start()
        self._app_runner = app_runner
        auth = "api-key" if self._api_keys else "open"
        logger.info(
            "Automation event server listening on http://%s:%s (%s)",
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
            logger.error("Automation event server failed to start: %s", error)

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

    async def _handle_event(self, request: web.Request) -> web.Response:
        """Run enabled automations matching the event name in the URL.

        Args:
            request: The incoming ``POST /event/{name}`` request.

        Returns:
            JSON summary of executed results, or a 4xx error response.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        name = request.match_info.get("name", "")
        payload = await self._read_payload(request)
        if payload is None:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        matches = [
            info
            for info in self._manager.get_event_automations(name)
            if self._manager.is_enabled(info.path)
        ]
        if not matches:
            return web.json_response(
                {"error": f"No enabled automation for event '{name}'."}, status=404
            )

        results = []
        for info in matches:
            result = await self._runner.run(info, payload)
            self._manager.record_run(info.path, result.timestamp)
            try:
                self._on_result(result)
            except Exception as error:  # pragma: no cover - defensive
                logger.error("Automation result callback failed: %s", error)
            results.append(
                {
                    "task": result.task,
                    "path": result.path,
                    "kind": result.kind.value,
                    "message": result.message,
                }
            )
        return web.json_response({"event": name, "results": results})

    # ------------------------------------------------------------------
    #  Private: Request helpers
    # ------------------------------------------------------------------

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
