"""Automation runner — loads an ``AUTOMATION.py`` and executes its ``run(ctx)``.

Frontmatter is stripped before the code body is compiled and executed, so an
``AUTOMATION.py`` is not importable as a plain module.  The runner captures
stdout/stderr plus the context log, normalises the returned dict into an
:class:`AutomationResult`, and coerces any exception into an ``error`` result.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import logging
from pathlib import Path
import time
import traceback
from typing import TYPE_CHECKING, Any

import frontmatter

from .context import AutomationContext
from .models import AutomationInfo, AutomationResult, AutomationResultKind

if TYPE_CHECKING:
    from ..app import ProcooApp

logger = logging.getLogger("procoo_qt")

#: Hard timeout for a single automation run, in seconds.
AUTOMATION_TIMEOUT_SEC = 1800


class AutomationRunner:
    """Loads and executes automations in-process on the qasync event loop."""

    def __init__(self, app: ProcooApp) -> None:
        """Initialise the runner.

        Args:
            app: The backend application holding config and skill subsystems.
        """
        self._app = app

    # ------------------------------------------------------------------
    #  Public
    # ------------------------------------------------------------------

    async def run(
        self, automation: AutomationInfo, payload: dict[str, Any] | None = None
    ) -> AutomationResult:
        """Execute an automation and return its normalised result.

        Args:
            automation: The automation to run.
            payload: Optional event payload exposed via ``ctx.payload``.

        Returns:
            An :class:`AutomationResult` describing success, info, or error.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_buffer = io.StringIO()

        try:
            run_fn = await asyncio.to_thread(self._compile_run_function, automation)
        except Exception as exc:
            logger.error("Automation '%s' failed to load: %s", automation.path, exc)
            return self._error_result(
                automation,
                timestamp,
                f"Failed to load automation: {exc}",
                traceback.format_exc(),
            )

        ctx = AutomationContext(
            automation,
            self._app.config,
            self._app.skill_manager,
            self._app.config.skills_dir,
            payload,
            media_dir=str(self._app.chat_store.storage_dir / "media"),
        )

        try:
            with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
                raw = await asyncio.wait_for(run_fn(ctx), timeout=AUTOMATION_TIMEOUT_SEC)
        except TimeoutError:
            log = self._combine_log(log_buffer, ctx, "")
            return self._error_result(
                automation,
                timestamp,
                f"Automation timed out after {AUTOMATION_TIMEOUT_SEC}s.",
                log,
            )
        except Exception as exc:
            logger.error("Automation '%s' raised: %s", automation.path, exc)
            log = self._combine_log(log_buffer, ctx, traceback.format_exc())
            return self._error_result(
                automation,
                timestamp,
                str(exc) or type(exc).__name__,
                log,
            )

        kind, message, data = self._normalize(raw)
        log = self._combine_log(log_buffer, ctx, "")
        logger.info("Automation '%s' finished: %s", automation.path, kind)
        return AutomationResult(
            kind=kind,
            path=automation.path,
            task=automation.name,
            message=message,
            log=log,
            data=data,
            timestamp=timestamp,
        )

    # ------------------------------------------------------------------
    #  Private: Loading
    # ------------------------------------------------------------------

    def _compile_run_function(self, automation: AutomationInfo) -> Callable:
        """Read, strip frontmatter, exec the code body, and return ``run``.

        Args:
            automation: The automation whose ``AUTOMATION.py`` to load.

        Returns:
            The automation's ``async def run(ctx)`` callable.

        Raises:
            RuntimeError: If no ``run`` function exists or it is not async.
        """
        auto_file = Path(automation.directory) / "AUTOMATION.py"
        source = auto_file.read_text(encoding="utf-8")
        code = frontmatter.loads(source).content
        namespace: dict[str, Any] = {
            "__name__": "procoo_automation",
            "__file__": str(auto_file),
        }
        compiled = compile(code, str(auto_file), "exec")
        exec(compiled, namespace)

        run_fn = namespace.get("run")
        if run_fn is None:
            raise RuntimeError("AUTOMATION.py must define an async run(ctx) function.")
        if not inspect.iscoroutinefunction(run_fn):
            raise RuntimeError("AUTOMATION.py run() must be declared with 'async def'.")
        return run_fn

    # ------------------------------------------------------------------
    #  Private: Result normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(raw: Any) -> tuple[AutomationResultKind, str, Any]:
        """Normalise a run() return value into ``(kind, message, data)``.

        Args:
            raw: The value returned by the automation.

        Returns:
            A tuple of result kind, message, and optional data.  Invalid shapes
            become an ``error`` result.
        """
        if raw is None:
            return AutomationResultKind.SUCCESS, "", None
        if isinstance(raw, str):
            return AutomationResultKind.SUCCESS, raw, None
        if isinstance(raw, dict):
            status = str(raw.get("status", "")).strip().lower()
            message = str(raw.get("message", ""))
            data = raw.get("data")
            try:
                return AutomationResultKind(status), message, data
            except ValueError:
                return (
                    AutomationResultKind.ERROR,
                    f"Invalid automation result status: '{status}'.",
                    None,
                )
        return (
            AutomationResultKind.ERROR,
            f"Invalid automation return type: {type(raw).__name__}.",
            None,
        )

    def _error_result(
        self, automation: AutomationInfo, timestamp: str, message: str, log: str
    ) -> AutomationResult:
        """Build an ``error`` result for the given automation.

        Args:
            automation: The automation that failed.
            timestamp: Completion timestamp.
            message: Error brief shown to the user.
            log: Accumulated run log / traceback.

        Returns:
            An :class:`AutomationResult` with ``kind == error``.
        """
        return AutomationResult(
            kind=AutomationResultKind.ERROR,
            path=automation.path,
            task=automation.name,
            message=message,
            log=log,
            data=None,
            timestamp=timestamp,
        )

    @staticmethod
    def _combine_log(buffer: io.StringIO, ctx: AutomationContext, extra: str) -> str:
        """Join captured stdout/stderr, the context log, and extra text.

        Args:
            buffer: The stdout/stderr capture buffer.
            ctx: The automation context holding explicit log lines.
            extra: Extra text (usually a traceback) appended last.

        Returns:
            The combined, right-stripped log string.
        """
        parts = [buffer.getvalue().strip(), ctx.log_text.strip()]
        if extra:
            parts.append(extra.strip())
        return "\n".join(part for part in parts if part)
