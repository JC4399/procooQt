"""Automation scheduler — fires scheduled automations on their cron times.

A single asyncio task waits for the nearest next-run time across all enabled
scheduled automations, runs due ones sequentially through the
:class:`AutomationRunner`, records their last-run state, and forwards each
result to the notification callback.  The loop is woken early via
:meth:`notify_changed` whenever automations are added, removed, or toggled.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from croniter import croniter

from .models import AutomationResult

if TYPE_CHECKING:
    from .manager import AutomationManager
    from .models import AutomationInfo
    from .runner import AutomationRunner

logger = logging.getLogger("procoo_qt")


class AutomationScheduler:
    """Fires enabled cron-scheduled automations and reports their results."""

    def __init__(
        self,
        manager: AutomationManager,
        runner: AutomationRunner,
        on_result: Callable[[AutomationResult], None],
    ) -> None:
        """Initialise the scheduler.

        Args:
            manager: Provides scheduled automations and records run state.
            runner: Executes automations.
            on_result: Callback invoked with each completed ``AutomationResult``.
        """
        self._manager = manager
        self._runner = runner
        self._on_result = on_result
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._wake = asyncio.Event()

    # ------------------------------------------------------------------
    #  Public: Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler loop if it is not already running."""
        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.ensure_future(self._loop())
        logger.info("Automation scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler loop and await its task."""
        self._stopped.set()
        self._wake.set()
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        logger.info("Automation scheduler stopped")

    def notify_changed(self) -> None:
        """Wake the loop so schedules are recomputed after a change."""
        self._wake.set()

    # ------------------------------------------------------------------
    #  Public: Manual run
    # ------------------------------------------------------------------

    async def run_now(self, automation: AutomationInfo) -> AutomationResult:
        """Run an automation immediately, bypassing its schedule.

        Args:
            automation: The automation to execute.

        Returns:
            The automation's result.
        """
        return await self._execute(automation)

    # ------------------------------------------------------------------
    #  Private: Main loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Wait for the next due time, then run due automations."""
        try:
            while not self._stopped.is_set():
                jobs = self._enabled_scheduled()
                next_time = self._nearest_time(jobs)
                delay = (
                    None if next_time is None else max(0.0, next_time - datetime.now().timestamp())
                )
                woken = await self._wait(delay)
                if woken or self._stopped.is_set():
                    continue
                await self._run_due()
        except asyncio.CancelledError:
            pass
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Automation scheduler crashed: %s", error)

    async def _run_due(self) -> None:
        """Run every enabled scheduled automation whose next time has passed."""
        now = datetime.now().timestamp()
        for automation in self._enabled_scheduled():
            fire_time = self._next_time(automation)
            if fire_time is not None and fire_time <= now:
                await self._execute(automation)

    async def _execute(self, automation: AutomationInfo) -> AutomationResult:
        """Run one automation, record its run, and forward the result.

        Args:
            automation: The automation to execute.

        Returns:
            The automation's result.
        """
        logger.info("Automation scheduler running '%s'", automation.path)
        result = await self._runner.run(automation)
        self._manager.record_run(automation.path, result.timestamp)
        try:
            self._on_result(result)
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Automation result callback failed: %s", error)
        logger.info("Automation scheduler finished '%s' with %s", automation.path, result.kind)
        return result

    # ------------------------------------------------------------------
    #  Private: Scheduling helpers
    # ------------------------------------------------------------------

    def _enabled_scheduled(self) -> list[AutomationInfo]:
        """Return enabled scheduled automations."""
        return [
            info
            for info in self._manager.scheduled_automations()
            if self._manager.is_enabled(info.path)
        ]

    def _next_time(self, automation: AutomationInfo) -> float | None:
        """Return the next fire timestamp for an automation, or ``None``."""
        try:
            next_dt = croniter(automation.schedule, datetime.now()).get_next(datetime)
            return next_dt.timestamp()
        except (ValueError, KeyError) as error:
            logger.warning("Invalid schedule for automation '%s': %s", automation.path, error)
            return None

    def _nearest_time(self, automations: list[AutomationInfo]) -> float | None:
        """Return the earliest next fire time across automations, or ``None``."""
        times = [t for info in automations if (t := self._next_time(info)) is not None]
        return min(times) if times else None

    async def _wait(self, delay: float | None) -> bool:
        """Wait for *delay* seconds, or until woken / stopped.

        Args:
            delay: Seconds to wait, or ``None`` to wait indefinitely.

        Returns:
            ``True`` when woken by :meth:`notify_changed`, ``False`` on timeout.
        """
        self._wake.clear()
        stop_waiter = asyncio.ensure_future(self._stopped.wait())
        wake_waiter = asyncio.ensure_future(self._wake.wait())
        try:
            done, _ = await asyncio.wait(
                {stop_waiter, wake_waiter},
                timeout=delay,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            stop_waiter.cancel()
            wake_waiter.cancel()
        return wake_waiter in done
