"""``SubAgentController`` — owns the local sub-agent HTTP server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot

from ..subagent.server import SubAgentServer

if TYPE_CHECKING:
    from ..app import ProcooApp

logger = logging.getLogger("procoo_qt")


class SubAgentController(QObject):
    """Lifecycle owner for the sub-agent HTTP server.

    Attributes:
        app: The backend application (config/sub-agent manager).
    """

    if TYPE_CHECKING:
        app: ProcooApp
        _server: SubAgentServer | None

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the controller.

        Args:
            app: The top-level application holding backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._server = None

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Construct the sub-agent server from config (not yet started)."""
        if not self.app.config.subagent_enabled:
            logger.info("Sub-agent server disabled by config")
            return
        self._server = SubAgentServer(
            self.app.config.subagent_host,
            self.app.config.subagent_port,
            self.app.config.subagent_api_keys,
            self.app.subagent_manager,
        )

    # ------------------------------------------------------------------
    #  Slot: Start
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Start the sub-agent HTTP server on the running event loop."""
        if self._server is None:
            self.build()
        if self._server is not None:
            self._server.start()

    # ------------------------------------------------------------------
    #  Slot: Stop
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Stop the sub-agent HTTP server."""
        if self._server is not None:
            await self._server.stop()
