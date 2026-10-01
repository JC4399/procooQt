"""``ControlController`` — owns the external session/window control HTTP server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot

from ..control.server import ControlServer

if TYPE_CHECKING:
    from ..app import ProcooApp
    from .window_manager import WindowManager

logger = logging.getLogger("procoo_qt")


class ControlController(QObject):
    """Lifecycle owner for the control HTTP server.

    Attributes:
        app: The backend application (config/chat store).
    """

    if TYPE_CHECKING:
        app: ProcooApp
        _windows: WindowManager
        _server: ControlServer | None

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(
        self,
        app: ProcooApp,
        windows: WindowManager,
        parent: QObject | None = None,
    ) -> None:
        """Initialise the control controller.

        Args:
            app: The top-level application holding backend subsystems.
            windows: The window manager the server operates on.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._windows = windows
        self._server = None

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Construct the control server from config (not yet started)."""
        self._server = ControlServer(
            self.app.config.control_server_host,
            self.app.config.control_server_port,
            self.app.config.control_server_api_keys,
            self.app.chat_store,
            self._windows,
        )

    # ------------------------------------------------------------------
    #  Slot: Start
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Start the control HTTP server on the running event loop."""
        if self._server is None:
            self.build()
        if self._server is not None:
            self._server.start()

    # ------------------------------------------------------------------
    #  Slot: Stop
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Stop the control HTTP server."""
        if self._server is not None:
            await self._server.stop()
