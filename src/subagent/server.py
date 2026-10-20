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
from .models import SubAgentSpec, SubAgentStatus

if TYPE_CHECKING:
    from .manager import SubAgentManager

logger = logging.getLogger("procoo_qt")


class SubAgentServer:
    """HTTP server exposing create, status, list, and cancel endpoints."""

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
            manager: The manager that owns sub-agent records and tasks.
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
        app.router.add_post("/subagents", self._handle_spawn)
        app.router.add_post("/subagents/batch", self._handle_spawn_batch)
        app.router.add_post("/subagents/run", self._handle_run)
        app.router.add_get("/subagents", self._handle_list)
        app.router.add_get("/subagents/{agent_id}", self._handle_get)
        app.router.add_post("/subagents/{agent_id}/cancel", self._handle_cancel)
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

    async def _handle_spawn(self, request: web.Request) -> web.Response:
        """Create and schedule one sub-agent.

        Args:
            request: A ``POST /subagents`` request carrying a spec body.

        Returns:
            The queued record with status 202, or a 4xx error.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        payload = await self._read_payload(request)
        if payload is None:
            return web.json_response({"error": "invalid JSON body"}, status=400)
        try:
            spec = SubAgentSpec(**payload)
            record = self._manager.create(spec)
        except (ValidationError, TypeError) as error:
            return self._validation_error(error)
        except SubAgentError as error:
            return self._subagent_error(error)
        return web.json_response(record.model_dump(mode="json"), status=202)

    async def _handle_spawn_batch(self, request: web.Request) -> web.Response:
        """Create and schedule multiple sub-agents from one request.

        Args:
            request: A ``POST /subagents/batch`` request with ``{specs, wait}``.

        Returns:
            ``{"records": [...]}``, or a 4xx error.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        payload = await self._read_payload(request)
        if payload is None:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        raw_specs = payload.get("specs")
        if not isinstance(raw_specs, list) or not raw_specs:
            return web.json_response({"error": "specs must be a non-empty list"}, status=400)
        should_wait = bool(payload.get("wait", False))

        records = []
        for index, raw_spec in enumerate(raw_specs):
            try:
                spec = SubAgentSpec(**raw_spec)
                records.append(self._manager.create(spec))
            except (ValidationError, TypeError) as error:
                return self._validation_error(error, index=index)
            except SubAgentError as error:
                return self._subagent_error(error, index=index)

        if should_wait:
            waited = await asyncio.gather(*(self._manager.wait(r.id) for r in records))
            records = [record for record in waited if record is not None]
        return web.json_response(
            {"records": [record.model_dump(mode="json") for record in records]},
            status=202 if not should_wait else 200,
        )

    async def _handle_run(self, request: web.Request) -> web.Response:
        """Create a sub-agent and block until it finishes.

        Args:
            request: A ``POST /subagents/run`` request carrying a spec body.

        Returns:
            The terminal record, or a 4xx error.
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
        return web.json_response(record.model_dump(mode="json"))

    async def _handle_get(self, request: web.Request) -> web.Response:
        """Return one sub-agent record.

        Args:
            request: A ``GET /subagents/{id}`` request.

        Returns:
            The record, or a 404 error.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        record = self._manager.get(request.match_info.get("agent_id", ""))
        if record is None:
            return web.json_response({"error": "sub-agent not found"}, status=404)
        return web.json_response(record.model_dump(mode="json"))

    async def _handle_list(self, request: web.Request) -> web.Response:
        """Return every retained sub-agent record.

        Args:
            request: A ``GET /subagents`` request, optionally with ``?status=``.

        Returns:
            ``{"records": [...]}``, or a 400 error for an invalid status.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        status_filter = str(request.query.get("status", "")).strip().lower()
        records = self._manager.list_records()
        if status_filter:
            try:
                wanted = SubAgentStatus(status_filter)
            except ValueError:
                return web.json_response({"error": f"invalid status: {status_filter}"}, status=400)
            records = [record for record in records if record.status == wanted]
        return web.json_response(
            {"records": [record.model_dump(mode="json") for record in records]}
        )

    async def _handle_cancel(self, request: web.Request) -> web.Response:
        """Cancel a queued or running sub-agent.

        Args:
            request: A ``POST /subagents/{id}/cancel`` request.

        Returns:
            The updated record, or a 404 error.
        """
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        record = await self._manager.cancel(request.match_info.get("agent_id", ""))
        if record is None:
            return web.json_response({"error": "sub-agent not found"}, status=404)
        return web.json_response(record.model_dump(mode="json"))

    # ------------------------------------------------------------------
    #  Private: Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validation_error(
        error: ValidationError | TypeError, index: int | None = None
    ) -> web.Response:
        """Build a 400 response for an invalid spec.

        Args:
            error: The pydantic validation error or request-shape error.
            index: Optional batch index.

        Returns:
            A JSON error response.
        """
        prefix = f"specs[{index}]: " if index is not None else ""
        return web.json_response(
            {"error": f"{prefix}{error}"},
            status=400,
        )

    @staticmethod
    def _subagent_error(error: SubAgentError, index: int | None = None) -> web.Response:
        """Build a 400 response for a rejected sub-agent request.

        Args:
            error: The manager error.
            index: Optional batch index.

        Returns:
            A JSON error response.
        """
        prefix = f"specs[{index}]: " if index is not None else ""
        return web.json_response(
            {"error": f"{prefix}{error.brief}", "detail": error.detail},
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
