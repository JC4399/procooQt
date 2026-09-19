"""Procoo Qt application — wiring, qasync event loop, and QML bootstrap."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication
import qasync

from .config.manager import ConfigManager
from .qt.ui import ProcooQtUI
from .session.store import SessionStore
from .skill.manager import SkillManager
from .skill.preset import PresetStore
from .util.error.types import ProcooError
from .util.log.formatter import setup_colored_logging

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger("procoo_qt")


class ProcooApp:
    """Top-level backend wiring for config, skill, session, and preset subsystems.

    Attributes:
        config: The ``ConfigManager`` holding LLM/path settings.
        skill_manager: The ``SkillManager`` for discovering and loading skills.
        session_store: The ``SessionStore`` for persisting session data.
        preset_store: The ``PresetStore`` for skill/tool preset configurations.
    """

    def __init__(self, config_dir: str = "./config") -> None:
        """Initialise the backend subsystems.

        Args:
            config_dir: Directory containing ``config.yaml``.
        """
        self.config = ConfigManager(config_dir)
        skills_dir = self._resolve(self.config.skills_dir)
        self.skill_manager = SkillManager(skills_dir)
        self.session_store = SessionStore(self._resolve(self.config.storage_dir))
        self.preset_store = PresetStore(str(Path(skills_dir) / "_presets"))

    # ------------------------------------------------------------------
    #  Private
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve(path_str: str) -> str:
        """Resolve a possibly-relative config path against the project root.

        Args:
            path_str: A path from ``config.yaml``.

        Returns:
            An absolute, resolved path string.
        """
        path = Path(path_str)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return str(path.resolve())


def _register_fonts() -> None:
    """Register the bundled monospace font with Qt."""
    font_path = _PROJECT_ROOT / "assets" / "fonts" / "SarasaFixedTC-Regular.ttf"
    if font_path.is_file():
        QFontDatabase.addApplicationFont(str(font_path))
        logger.info("Registered font: %s", font_path.name)
    else:
        logger.warning("Font not found: %s", font_path)


def main() -> None:
    """Launch the Procoo Qt application."""
    setup_colored_logging(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        backend = ProcooApp(str(_PROJECT_ROOT / "config"))
    except ProcooError as error:
        logger.critical("[CONFIG] %s", error.detail)
        sys.exit(1)
    logger.info(
        "Config: api_base=%s model=%s",
        backend.config.llm_api_base,
        backend.config.llm_model_name,
    )

    QQuickStyle.setStyle("Basic")
    qt_app = QApplication(sys.argv)
    _register_fonts()

    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    engine = QQmlApplicationEngine()
    ui = ProcooQtUI(backend, engine)
    main_qml = _PROJECT_ROOT / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        logger.critical("Failed to load QML: %s", main_qml)
        sys.exit(1)

    ui.start()
    logger.info("Procoo Qt started (ui=%s)", type(ui).__name__)
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
