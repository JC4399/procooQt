"""Automation scheduler — fires scheduled automations on their cron times.

A single asyncio task waits for the nearest next-run time across all enabled
scheduled automations, runs due ones sequentially through the
:class:`AutomationRunner`, records their last-run state, and forwards each
result to the notification callback.  The loop is woken early via
:meth:`notify_changed` whenever automations are added, removed, or toggled.

Automations may declare an optional ``start_date`` / ``end_date`` window in
their frontmatter: firing is skipped before the start date, and automations
are auto-disabled once the end date has passed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from croniter import croniter

from .models import AutomationResult, parse_iso_date

if TYPE_CHECKING:
    from .manager import AutomationManager
    from .models import AutomationInfo
    from .runner import AutomationRunner

logger = logging.getLogger("procoo_qt")

_EARLY_FIRE_TOLERANCE_SEC = 2.0


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
                self._wake.clear()
                self._auto_disable_expired()
                jobs = self._enabled_scheduled()
                fire_times = self._fire_times(jobs)
                next_time = self._nearest_time(jobs)
                delay = (
                    None if next_time is None else max(0.0, next_time - datetime.now().timestamp())
                )
                woken = await self._wait(delay)
                if woken or self._stopped.is_set():
                    continue
                await self._run_due(jobs, fire_times)
        except asyncio.CancelledError:
            pass
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Automation scheduler crashed: %s", error)

    async def _run_due(self, jobs: list[AutomationInfo], fire_times: dict[str, float]) -> None:
        """Run automations whose planned fire time has arrived.

        Fire times are the ones planned before the wait: recomputing them after
        the wait would return the *next* occurrence and skip the current one.

        Args:
            jobs: The enabled scheduled automations considered before the wait.
            fire_times: Planned fire timestamp per automation path.
        """
        for automation in jobs:
            planned = fire_times.get(automation.path)
            if planned is None or not self._manager.is_enabled(automation.path):
                continue
            remaining = planned - datetime.now().timestamp()
            if remaining > _EARLY_FIRE_TOLERANCE_SEC:
                continue
            if remaining > 0:
                await asyncio.sleep(remaining)
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

    def _auto_disable_expired(self) -> None:
        """Disable enabled scheduled automations whose end date has passed."""
        today = datetime.now().date()
        for info in self._manager.scheduled_automations():
            end = parse_iso_date(info.end_date)
            if end is None or today <= end or not self._manager.is_enabled(info.path):
                continue
            logger.info(
                "Automation '%s' auto-disabled: end date %s passed", info.path, info.end_date
            )
            self._manager.set_enabled(info.path, False)

    def _in_window(self, automation: AutomationInfo) -> bool:
        """Return whether the automation's date window covers today.

        Automations without dates are always in window.

        Args:
            automation: The automation to check.

        Returns:
            ``True`` when today is within ``[start_date, end_date]``.
        """
        today = datetime.now().date()
        start = parse_iso_date(automation.start_date)
        end = parse_iso_date(automation.end_date)
        if start is not None and today < start:
            return False
        return not (end is not None and today > end)

    def _next_time(self, automation: AutomationInfo) -> float | None:
        """Return the next fire timestamp for an automation, or ``None``.

        Returns ``None`` while the automation is outside its date window
        (before ``start_date`` or after ``end_date``).

        Args:
            automation: The automation to evaluate.

        Returns:
            The next fire timestamp, or ``None`` when out of window or the
            cron expression is invalid.
        """
        if not self._in_window(automation):
            return None
        try:
            next_dt = croniter(automation.schedule, datetime.now()).get_next(datetime)
            return next_dt.timestamp()
        except (ValueError, KeyError) as error:
            logger.warning("Invalid schedule for automation '%s': %s", automation.path, error)
            return None

    def _wake_time(self, automation: AutomationInfo) -> float | None:
        """Return when the loop should next wake for an automation.

        Unlike :meth:`_next_time`, a future automation wakes the loop at its
        window start so the schedule is re-evaluated on the day it activates.

        Args:
            automation: The automation to evaluate.

        Returns:
            The next wake timestamp, or ``None`` when expired or unschedulable.
        """
        start = parse_iso_date(automation.start_date)
        if start is not None and datetime.now().date() < start:
            return datetime(start.year, start.month, start.day).timestamp()
        return self._next_time(automation)

    def _fire_times(self, automations: list[AutomationInfo]) -> dict[str, float]:
        """Return the planned next fire timestamp per automation path.

        Args:
            automations: The automations to evaluate.

        Returns:
            A mapping of automation path to its next fire timestamp
            (automations outside their date window are omitted).
        """
        return {info.path: t for info in automations if (t := self._next_time(info)) is not None}

    def _nearest_time(self, automations: list[AutomationInfo]) -> float | None:
        """Return the earliest next wake time across automations, or ``None``."""
        times = [t for info in automations if (t := self._wake_time(info)) is not None]
        return min(times) if times else None

    async def _wait(self, delay: float | None) -> bool:
        """Wait for *delay* seconds, or until woken / stopped.

        Args:
            delay: Seconds to wait, or ``None`` to wait indefinitely.

        Returns:
            ``True`` when woken by :meth:`notify_changed`, ``False`` on timeout.
        """
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
