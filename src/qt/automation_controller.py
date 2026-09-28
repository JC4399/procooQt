"""``AutomationController`` — automation cards, toggles, scheduler, and event server.

Owns the automation subsystem runtime: the list model behind the automation page,
the fuzzy search filter, enable/disable toggles, manual runs, and the lifecycle of
the cron scheduler and the inbound HTTP event server.  Completed runs are emitted
as :attr:`result_ready` for the notification controller, and the editor is opened
through :attr:`edit_automation_requested`.

The ``watchdog`` callback runs on a background thread and only emits
:attr:`files_changed`; the connected slot then refreshes off-loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..automation.runner import AutomationRunner
from ..automation.scheduler import AutomationScheduler
from ..automation.server import AutomationEventServer
from .error_handler import TOAST_ERROR
from .models.automation_list_model import AutomationListModel

if TYPE_CHECKING:
    from ..app import ProcooApp
    from ..automation.models import AutomationResult

logger = logging.getLogger("procoo_qt")


class AutomationController(QObject):
    """Automation page controller owning discovery state, scheduler, and server."""

    automations_changed = Signal()
    files_changed = Signal()
    result_ready = Signal(object)
    edit_automation_requested = Signal(str)
    toast_requested = Signal(str, str)

    if TYPE_CHECKING:
        # Attributes provided by ui.py orchestrator
        app: ProcooApp

        # Attributes owned by this controller
        _model: AutomationListModel
        _runner: AutomationRunner
        _scheduler: AutomationScheduler
        _server: AutomationEventServer
        _search_text: str
        _tasks: set[asyncio.Task[Any]]
        _running: set[str]

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the automation controller.

        Args:
            app: The top-level application holding backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._tasks: set[asyncio.Task[Any]] = set()
        self._running: set[str] = set()

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the model, runner, scheduler, and event server."""
        self._model = AutomationListModel(self)
        self._search_text = ""
        self._runner = AutomationRunner(self.app)
        manager = self.app.automation_manager
        self._scheduler = AutomationScheduler(manager, self._runner, self._on_result)
        self._server = AutomationEventServer(
            self.app.config.server_host,
            self.app.config.server_port,
            self.app.config.api_keys,
            manager,
            self._runner,
            self._on_result,
        )
        self.files_changed.connect(self._handle_files_changed)
        self._rebuild()

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=automations_changed)
    def automation_model(self) -> AutomationListModel:
        """Return the automation list model.

        Returns:
            The model exposed to QML as ``automation.automation_model``.
        """
        return self._model

    @Property(str, notify=automations_changed)
    def searchText(self) -> str:  # noqa: N802
        """Return the current automation search term.

        Returns:
            The active fuzzy filter, or an empty string.
        """
        return self._search_text

    # ------------------------------------------------------------------
    #  Slot: Start
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Start watching automations, the scheduler, and the event server."""
        self.app.automation_manager.start_watching(self._on_files_changed)
        self._scheduler.start()
        self._server.start()

    # ------------------------------------------------------------------
    #  Slot: Search
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_search_changed(self, text: str) -> None:
        """Re-filter the automation list as the search field changes.

        Args:
            text: The current search field text.
        """
        self._search_text = (text or "").strip()
        self._rebuild()

    # ------------------------------------------------------------------
    #  Slot: Enable / disable
    # ------------------------------------------------------------------

    @Slot(str, bool)
    def _handle_toggle(self, path: str, enabled: bool) -> None:
        """Enable or disable an automation and reschedule.

        Args:
            path: Relative automation path.
            enabled: The new enabled state.
        """
        self.app.automation_manager.set_enabled(path, enabled)
        self._scheduler.notify_changed()
        self._rebuild()

    # ------------------------------------------------------------------
    #  Slot: Edit / run now
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_edit(self, path: str) -> None:
        """Request the editor to open an automation folder.

        Args:
            path: Relative automation path.
        """
        self.edit_automation_requested.emit(path)

    @Slot(str)
    def _handle_run_now(self, path: str) -> None:
        """Run an automation immediately.

        Args:
            path: Relative automation path.
        """
        self._spawn(self._run_now(path))

    async def _run_now(self, path: str) -> None:
        """Execute an automation on demand and publish its result.

        Marks the automation as running so its card shows a spinner and disables
        the button for the duration of the run.

        Args:
            path: Relative automation path.
        """
        info = self.app.automation_manager.get_automation(path)
        if info is None:
            self.toast_requested.emit("Automation not found.", TOAST_ERROR)
            return
        self._running.add(path)
        self._model.set_running(path, True)
        try:
            result = await self._runner.run(info)
            self.app.automation_manager.record_run(path, result.timestamp)
        finally:
            self._running.discard(path)
            self._model.set_running(path, False)
        self._on_result(result)

    # ------------------------------------------------------------------
    #  Result callback
    # ------------------------------------------------------------------

    def _on_result(self, result: AutomationResult) -> None:
        """Forward a completed automation result and refresh the list.

        Args:
            result: The completed automation result.
        """
        self.result_ready.emit(result)
        self._rebuild()

    # ------------------------------------------------------------------
    #  Watcher
    # ------------------------------------------------------------------

    def _on_files_changed(self) -> None:
        """Watchdog callback (background thread) — emit only, never touch models."""
        self.files_changed.emit()

    @Slot()
    def _handle_files_changed(self) -> None:
        """Refresh automation data after a watchdog event (GUI thread)."""
        self._spawn(self._refresh())

    async def _refresh(self) -> None:
        """Re-scan automations off-loop, then rebuild and reschedule."""
        try:
            await asyncio.to_thread(self.app.automation_manager.refresh)
        except Exception as error:
            logger.error("Automation refresh failed: %s", error)
            self.toast_requested.emit("Failed to refresh automations.", TOAST_ERROR)
            return
        self._scheduler.notify_changed()
        self._rebuild()

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Rebuild the automation model from the manager and current search."""
        self._model.set_automations(
            self.app.automation_manager.automations, self._search_text, self._running
        )
        self.automations_changed.emit()

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Schedule a coroutine and keep a reference until it completes.

        Args:
            coro: The coroutine to schedule on the running event loop.
        """
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        task.add_done_callback(self._log_task_failure)

    @staticmethod
    def _log_task_failure(task: asyncio.Task[Any]) -> None:
        """Log an unexpected background task failure.

        Args:
            task: The completed task.
        """
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("Automation background task failed: %s", error)
