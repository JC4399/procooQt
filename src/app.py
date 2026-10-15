"""Procoo Qt application — wiring, qasync event loop, and QML bootstrap."""

from __future__ import annotations

import asyncio
import ctypes
import logging
from pathlib import Path
import sys
from typing import cast

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFontDatabase, QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication
import qasync

from .automation.manager import AutomationManager
from .chat.store import ChatStore
from .config.manager import ConfigManager
from .notification.manager import NotificationManager
from .qt import native_frame
from .qt.qasync_timer_fix import install_qasync_timer_patch
from .qt.ui import ProcooQtUI
from .skill.manager import SkillManager
from .skill.preset import PresetStore
from .util.error.types import ProcooError
from .util.log.formatter import setup_colored_logging

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger("procoo_qt")


class ProcooApp:
    """Top-level backend wiring for config, skill, chat, and preset subsystems.

    Attributes:
        config: The ``ConfigManager`` holding LLM/path settings.
        skill_manager: The ``SkillManager`` for discovering and loading skills.
        chat_store: The ``ChatStore`` for persisting chat data.
        preset_store: The ``PresetStore`` for skill/tool preset configurations.
        automation_manager: The ``AutomationManager`` for automation discovery/state.
        notification_manager: The ``NotificationManager`` for run-result history.
    """

    def __init__(self, config_dir: str = "./config") -> None:
        """Initialise the backend subsystems.

        Args:
            config_dir: Directory containing ``config.yaml``.
        """
        self.config = ConfigManager(config_dir)
        skills_dir = self._resolve(self.config.skills_dir)
        storage_dir = self._resolve(self.config.storage_dir)
        self.capabilities_dir = self._resolve(self.config.capabilities_dir)
        self.skill_manager = SkillManager(skills_dir)
        self.chat_store = ChatStore(storage_dir)
        self.preset_store = PresetStore(str(Path(skills_dir) / "_presets"))
        self.automation_manager = AutomationManager(
            self._resolve(self.config.automations_dir), storage_dir
        )
        self.notification_manager = NotificationManager(storage_dir)

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
    """Register the bundled Nerd Font monospace (text + icon glyphs) with Qt.

    The family name Qt reports depends on the platform plugin (Windows uses
    ``"Sarasa Fixed TC Nerd Font"``), so the resolved family is logged and
    checked against ``Theme.fontMono``; a mismatch would silently fall back to a
    proportional system font.
    """
    from .qt.theme import FONT_MONO

    font_path = _PROJECT_ROOT / "assets" / "fonts" / "sarasa-fixed-tc-regular-nerd-font.ttf"
    if not font_path.is_file():
        logger.warning("Font not found: %s", font_path)
        return
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
    logger.info("Registered font: %s -> %s", font_path.name, families)
    if FONT_MONO not in families:
        logger.warning(
            "Font family mismatch: Theme.fontMono=%r not in %s; text will fall back",
            FONT_MONO,
            families,
        )


def _set_app_user_model_id() -> None:
    """Give Windows a stable AppUserModelID so the taskbar uses the app icon."""
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("procoo.qt")


def _set_app_icon(qt_app: QApplication) -> None:
    """Set the application-wide window, title-bar, and taskbar icon.

    Args:
        qt_app: The running ``QApplication``.
    """
    icon_path = _PROJECT_ROOT / "assets" / "logos" / "logo.png"
    if icon_path.is_file():
        qt_app.setWindowIcon(QIcon(str(icon_path)))
        logger.info("Set application icon: %s", icon_path.name)
    else:
        logger.warning("Icon not found: %s", icon_path)


def main() -> None:
    """Launch the Procoo Qt application."""
    setup_colored_logging(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _set_app_user_model_id()

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
    qt_app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    _set_app_icon(qt_app)
    _register_fonts()

    # Free Qt timers as soon as an asyncio callback is cancelled; qasync 0.28.0
    # otherwise leaks a Win32 USER timer per streamed HTTP chunk (see module doc).
    install_qasync_timer_patch()

    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    engine = QQmlApplicationEngine()
    ui = ProcooQtUI(backend, engine, qt_app)
    main_qml = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        logger.critical("Failed to load QML: %s", main_qml)
        sys.exit(1)

    root_window = cast(QWindow, engine.rootObjects()[0])
    _native_frame = native_frame.install(qt_app, root_window)

    ui.start(root_window, _native_frame)
    logger.info("Procoo Qt started (ui=%s)", type(ui).__name__)
    with loop:
        loop.run_forever()
    ui.shutdown()


if __name__ == "__main__":
    main()
