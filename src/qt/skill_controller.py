"""``SkillController`` — skill tree, tool modes, presets, and live config sync.

Owns the skill tree and tool-mode models: the right sidebar's activated checkboxes,
per-tool allow/ask/block modes, preset load/save/delete, search filtering,
the active-config chip bar, and the config-sync flow that pushes selections to the
live chat and appends a delta context banner.

The skill watcher runs on a ``watchdog`` background thread. Its callback only emits
:attr:`skill_files_changed`; the connected slot runs queued on the GUI thread and
schedules an off-loop refresh with :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..chat.manager import chat_manager
from ..util.log.formatter import (
    format_preset_delete,
    format_preset_load,
    format_preset_save,
    format_skill_change,
    format_tool_change,
)
from .chat_worker import ChatWorker, get_worker
from .context_banner import build_delta_context_sections
from .error_handler import TOAST_ERROR, TOAST_INFO, TOAST_WARNING
from .models.skill_tree_model import SkillTreeModel
from .models.tool_mode_model import ToolModeModel
from .theme import (
    COLOR_CHIP_ACTIVATED_BG,
    COLOR_CHIP_ACTIVATED_FG,
    COLOR_CHIP_ALLOW_BG,
    COLOR_CHIP_ALLOW_FG,
    COLOR_CHIP_ASK_BG,
    COLOR_CHIP_ASK_FG,
    COLOR_CHIP_BLOCK_BG,
    COLOR_CHIP_BLOCK_FG,
)

if TYPE_CHECKING:
    from ..app import ProcooApp
    from .chat_controller import ChatController
    from .error_handler import ErrorNotifier
    from .session_controller import SessionController

logger = logging.getLogger("procoo_qt")

_CHIP_ACTIVATED = (COLOR_CHIP_ACTIVATED_BG, COLOR_CHIP_ACTIVATED_FG)
_MODE_CHIP_COLORS: dict[str, tuple[str, str]] = {
    "allow": (COLOR_CHIP_ALLOW_BG, COLOR_CHIP_ALLOW_FG),
    "ask": (COLOR_CHIP_ASK_BG, COLOR_CHIP_ASK_FG),
    "block": (COLOR_CHIP_BLOCK_BG, COLOR_CHIP_BLOCK_FG),
}


class SkillController(QObject):
    """Skill tree, tool permission, preset, and config-sync controller."""

    skills_changed = Signal()
    tool_modes_changed = Signal()
    presets_changed = Signal()
    config_changed = Signal()
    preset_name_changed = Signal()
    toast_requested = Signal(str, str)
    skill_files_changed = Signal()

    if TYPE_CHECKING:
        # Attributes provided by ui.py orchestrator
        app: ProcooApp

        # Attributes owned by this controller
        _skill_model: SkillTreeModel
        _tool_model: ToolModeModel
        _tool_modes: dict[str, str]
        _preset_names: list[str]
        _config_chips: list[dict[str, str]]
        _search_text: str
        _preset_name: str
        _loading_chat_config: bool
        _sidebar_chat_id: str
        _tasks: set[asyncio.Task[Any]]

        # Attributes provided by other controllers (composition)
        chat: ChatController
        notifier: ErrorNotifier
        session: SessionController

        # Cross-controller method stubs
        def rebuild_chat_display(self, chat_id: str) -> None: ...

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: ProcooApp, parent: QObject | None = None) -> None:
        """Initialise the skill controller.

        Args:
            app: The top-level application holding backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app
        self._tasks: set[asyncio.Task[Any]] = set()
        self._pending_config: dict[str, tuple] = {}

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the skill models, wire the watcher, and populate from disk."""
        self._skill_model = SkillTreeModel(self)
        self._tool_model = ToolModeModel(self)
        self._tool_modes = self.app.skill_manager.default_tool_modes()
        self._preset_names = []
        self._config_chips = []
        self._search_text = ""
        self._preset_name = ""
        self._loading_chat_config = False
        self._sidebar_chat_id = ""
        self.skill_files_changed.connect(self._handle_skill_files_changed)
        self._refresh_presets(emit=False)
        self._rebuild_skill_sidebar()
        self._update_config_chips()

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(QObject, notify=skills_changed)
    def skill_model(self) -> SkillTreeModel:
        """Return the flattened skill tree model.

        Returns:
            The model exposed to QML as ``skill.skill_model``.
        """
        return self._skill_model

    @Property(QObject, notify=tool_modes_changed)
    def tool_model(self) -> ToolModeModel:
        """Return the grouped tool-mode model.

        Returns:
            The model exposed to QML as ``skill.tool_model``.
        """
        return self._tool_model

    @Property(list, notify=presets_changed)
    def presetNames(self) -> list[str]:  # noqa: N802
        """Return saved preset names.

        Returns:
            Sorted list of preset names.
        """
        return self._preset_names

    @Property(list, notify=config_changed)
    def configChips(self) -> list[dict[str, str]]:  # noqa: N802
        """Return the active-config chip list.

        Returns:
            List of ``{"label", "bg", "fg"}`` chip dicts for the active chat.
        """
        return self._config_chips

    @Property(str, notify=skills_changed)
    def searchText(self) -> str:  # noqa: N802
        """Return the current skill search term.

        Returns:
            The active search filter, or an empty string.
        """
        return self._search_text

    @Property(str, notify=preset_name_changed)
    def presetName(self) -> str:  # noqa: N802
        """Return the preset name typed into the save field.

        Returns:
            The pending preset name.
        """
        return self._preset_name

    @presetName.setter
    def presetName(self, value: str) -> None:  # noqa: N802
        self._preset_name = value or ""
        self.preset_name_changed.emit()

    # ------------------------------------------------------------------
    #  Slot: Start
    # ------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Start watching the skills directory and load the active chat config."""
        self.app.skill_manager.start_watching(self._on_skill_files_changed)
        chat_id = self.session.active_chat_id
        if chat_id:
            self._handle_chat_activated(chat_id)

    # ------------------------------------------------------------------
    #  Slot: Chat activated
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_chat_activated(self, chat_id: str) -> None:
        """Load a newly activated chat's skill/tool config into the sidebar.

        The chat becomes the target for subsequent config-sync writes, so edits
        made in a panel's skill dock apply to that panel's own chat.

        Args:
            chat_id: The newly active chat id (empty when none).
        """
        self._sidebar_chat_id = chat_id or ""
        if not chat_id:
            self._loading_chat_config = True
            try:
                self._skill_model.apply_selection(set())
                self._apply_tool_modes({})
            finally:
                self._loading_chat_config = False
            self._refresh_tool_model()
            self._update_config_chips()
            return
        self._load_config_into_sidebar(chat_id)

    # ------------------------------------------------------------------
    #  Slot: Search
    # ------------------------------------------------------------------

    @Slot(str)
    def _handle_search_changed(self, text: str) -> None:
        """Re-filter the skill tree as the search field changes.

        Args:
            text: The current search field text.
        """
        self._search_text = (text or "").strip()
        self._skill_model.rebuild(self.app.skill_manager.get_skill_tree(), self._search_text)
        self.skills_changed.emit()

    @Slot()
    def _handle_clear_search(self) -> None:
        """Clear the search filter and show all skills."""
        self._handle_search_changed("")

    # ------------------------------------------------------------------
    #  Slot: Skill toggle
    # ------------------------------------------------------------------

    @Slot(str, bool)
    def _handle_skill_toggle(self, path: str, checked: bool) -> None:
        """Handle an activated checkbox toggle.

        Args:
            path: The skill's relative path.
            checked: The new checkbox state.
        """
        self._skill_model.set_selection(path, checked)
        self._refresh_tool_model()
        self.skills_changed.emit()
        if self._loading_chat_config:
            return
        display = self.app.skill_manager.path_to_display_name(path)
        logger.info("%s", format_skill_change(display, "activated", checked))
        self._schedule_sync()

    # ------------------------------------------------------------------
    #  Slot: Tool mode
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _handle_tool_mode_change(self, tool_name: str, mode: str) -> None:
        """Handle a tool mode radio selection.

        Args:
            tool_name: The tool whose mode changed.
            mode: The new mode (``"allow"``/``"ask"``/``"block"``).
        """
        if self._tool_modes.get(tool_name) == mode:
            return
        self._tool_modes[tool_name] = mode
        self._tool_model.set_mode(tool_name, mode)
        logger.info("%s", format_tool_change(tool_name, mode))
        if self._loading_chat_config:
            return
        self._schedule_sync()

    # ------------------------------------------------------------------
    #  Slot: Folder toggle
    # ------------------------------------------------------------------

    @Slot(str, bool)
    def _handle_folder_toggle(self, path: str, expanded: bool) -> None:
        """Expand or collapse a skill folder.

        Args:
            path: The folder's relative path.
            expanded: Whether the folder should be expanded.
        """
        self._skill_model.set_folder_expanded(path, expanded)
        self.skills_changed.emit()

    # ------------------------------------------------------------------
    #  Slot: Presets
    # ------------------------------------------------------------------

    @Slot()
    def _handle_save_preset(self) -> None:
        """Save the current sidebar selections as the typed preset name.

        The name comes from the :attr:`presetName` property, set by the QML field.
        """
        cleaned = self._preset_name.strip()
        if not cleaned:
            self.toast_requested.emit("Please enter a preset name.", TOAST_ERROR)
            return
        config = self._collect_sidebar_config()
        activated = config["activated"]
        tool_modes = self._collect_tool_modes()
        self.app.preset_store.save_preset(
            cleaned,
            {
                "activated_skills": activated,
                "tools": tool_modes,
            },
        )
        logger.info("%s", format_preset_save(cleaned, activated, tool_modes))
        self._preset_name = cleaned
        self.preset_name_changed.emit()
        self._refresh_presets()
        self.toast_requested.emit(f"Preset '{cleaned}' saved.", TOAST_INFO)

    @Slot(str)
    def _handle_load_preset(self, name: str) -> None:
        """Apply a preset's skill/tool selections to the sidebar.

        Args:
            name: The preset to load; an empty name clears all selections.
        """
        if not name:
            self._loading_chat_config = True
            try:
                self._skill_model.apply_selection(set())
                self._apply_tool_modes({})
            finally:
                self._loading_chat_config = False
            self._refresh_tool_model()
            self._update_config_chips()
            self.toast_requested.emit("Preset selections cleared.", TOAST_INFO)
            return

        preset = self.app.preset_store.load_preset(name)
        if not preset:
            self.toast_requested.emit(f"Preset '{name}' not found.", TOAST_WARNING)
            return
        activated = self._normalize_activated(
            preset.get("activated_skills", preset.get("primary_skills", [])) or []
        )
        tools = preset.get("tools", {})
        logger.info(
            "%s",
            format_preset_load(
                name,
                preset.get("activated_skills", preset.get("primary_skills", [])),
                tools,
            ),
        )
        self._loading_chat_config = True
        try:
            self._skill_model.apply_selection(activated)
            self._apply_tool_modes(tools)
        finally:
            self._loading_chat_config = False
        self._refresh_tool_model()
        self._update_config_chips()
        self._schedule_sync()
        self.toast_requested.emit(f"Preset '{name}' loaded.", TOAST_INFO)

    @Slot(str)
    def _handle_delete_preset(self, name: str) -> None:
        """Delete a preset.

        Args:
            name: The preset to delete.
        """
        if name:
            self.app.preset_store.delete_preset(name)
            logger.info("%s", format_preset_delete(name))
            if self._preset_name == name:
                self._preset_name = ""
                self.preset_name_changed.emit()
            self.toast_requested.emit(f"Preset '{name}' deleted.", TOAST_INFO)
        self._refresh_presets()

    # ------------------------------------------------------------------
    #  State: Collect selections (DRY — shared by sync and presets)
    # ------------------------------------------------------------------

    def _normalize_activated(self, paths: list[str]) -> set[str]:
        """Canonicalise stored or preset skill paths before applying them.

        Args:
            paths: Skill paths that may use Windows separators.

        Returns:
            Set of forward-slash skill paths.
        """
        manager = self.app.skill_manager
        return {manager.normalize_skill_path(path) for path in paths}

    def _collect_selected_skills(self) -> list[str]:
        """Read the current activated selections.

        Returns:
            Sorted list of activated skill paths.
        """
        return self._skill_model.collect_selected_activated()

    def _collect_tool_modes(self) -> dict[str, str]:
        """Read the current per-tool mode selections.

        Returns:
            Dict mapping tool name to mode.
        """
        return dict(self._tool_modes)

    def _collect_sidebar_config(self) -> dict[str, Any]:
        """Collect the sidebar selections into a chat config dict.

        Returns:
            Dict with ``activated`` and ``tools`` (tool config for the selected
            activated skills).
        """
        activated = self._collect_selected_skills()
        tool_config = self.app.skill_manager.build_tool_config(
            self._collect_tool_modes(), activated
        )
        return {
            "activated": activated,
            "tools": tool_config,
        }

    # ------------------------------------------------------------------
    #  Sync: config to chat
    # ------------------------------------------------------------------

    def _schedule_sync(self) -> None:
        """Schedule the config-sync coroutine on the running event loop."""
        self._spawn(self._sync_config_to_chat())

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
            logger.error("Skill background task failed: %s", error)

    async def _sync_config_to_chat(self) -> None:
        """Synchronise sidebar selections to the active chat.

        Persists the config, refreshes the chip bar, pushes the config to the live
        chat, surfaces warnings, appends a delta context banner, and rebuilds the
        active chat display.
        """
        if self._loading_chat_config:
            return
        chat_id = self._sidebar_chat_id
        if not chat_id:
            return
        config = self._collect_sidebar_config()
        old_tool_config = self._persist_config(chat_id, config)
        self._update_config_chips()
        self._publish_config_summary(chat_id, config)
        await self._apply_live_config(chat_id, config, old_tool_config)

    def _persist_config(self, chat_id: str, config: dict[str, Any]) -> dict[str, str]:
        """Persist the sidebar config to the chat store.

        Args:
            chat_id: The active chat id.
            config: The collected ``{activated, tools}`` config.

        Returns:
            The previous tool-mode mapping, used to compute mode changes.
        """
        stored = self.app.chat_store.load_chat(chat_id)
        if not stored:
            return {}
        old_tool_config = stored.get("skills_config", {}).get("tools", {})
        stored["skills_config"] = config
        self.app.chat_store.save_chat(chat_id, stored)
        return old_tool_config

    async def _apply_live_config(
        self,
        chat_id: str,
        config: dict[str, Any],
        old_tool_config: dict[str, str],
    ) -> None:
        """Push the config to the live chat and append a delta banner.

        Args:
            chat_id: The active chat id.
            config: The collected config dict.
            old_tool_config: The previous tool-mode mapping.
        """
        if chat_manager.get_chat(chat_id) is None:
            return
        activated, tool_defs, tool_config = await asyncio.to_thread(
            self._load_config_payloads, config
        )
        worker = get_worker(chat_id)
        if worker is None:
            return
        self._pending_config[chat_id] = (
            config,
            old_tool_config,
            activated,
            tool_defs,
        )
        worker.update_config(activated, tool_defs, tool_config)

    @Slot(str, object)
    def _handle_worker_config_updated(self, chat_id: str, result: object) -> None:
        """Append a delta context banner once a worker confirms a config change.

        Args:
            chat_id: The chat whose config changed.
            result: The ``update_skill_config`` result dict.
        """
        pending = self._pending_config.pop(chat_id, None)
        worker = get_worker(chat_id)
        for warning in cast(dict, result).get("warnings", []):
            self.toast_requested.emit(warning, TOAST_WARNING)
        if pending is not None and worker is not None:
            config, old_tool_config, activated, tool_defs = pending
            self._append_delta_banner(
                chat_id,
                config,
                old_tool_config,
                cast(dict, result),
                activated,
                tool_defs,
                worker,
            )
        if worker is not None:
            worker.request_rebuild()

    def _load_config_payloads(
        self, config: dict[str, Any]
    ) -> tuple[list[dict], list[dict], dict[str, str]]:
        """Load skill contents and tool definitions for a config (blocking I/O).

        Args:
            config: The collected ``{activated, tools}`` config.

        Returns:
            Tuple of activated contents, tool definitions, and the built tool-mode
            mapping.
        """
        manager = self.app.skill_manager
        activated = manager.load_skill_contents(config["activated"])
        tool_defs = manager.load_tool_functions(config["activated"])
        tool_config = manager.build_tool_config(config["tools"], config["activated"])
        return activated, tool_defs, tool_config

    def _append_delta_banner(
        self,
        chat_id: str,
        config: dict[str, Any],
        old_tool_config: dict[str, str],
        result: dict[str, Any],
        activated: list[dict],
        tool_defs: list[dict],
        worker: ChatWorker,
    ) -> None:
        """Append the latest delta context banner to the chat's worker.

        Args:
            chat_id: The active chat id.
            config: The collected config dict.
            old_tool_config: The previous tool-mode mapping.
            result: The ``update_chat_config`` result dict.
            activated: Loaded activated skill contents.
            tool_defs: Loaded tool definitions.
            worker: The chat's worker (owns the banner list).
        """
        added_activated = result.get("added_activated", [])
        added_tools = result.get("added_tools", [])
        added_activated_contents = [s for s in activated if s.get("path", "") in added_activated]
        added_tool_defs = [td for td in tool_defs if td.get("name", "") in added_tools]
        mode_changes: dict[str, tuple[str, str]] = {}
        for tool_name, new_mode in config["tools"].items():
            old_mode = old_tool_config.get(tool_name, "")
            if old_mode and old_mode != new_mode:
                mode_changes[tool_name] = (old_mode, new_mode)

        if added_activated or added_tools or mode_changes:
            sections = build_delta_context_sections(
                added_activated_contents, added_tool_defs, mode_changes
            )
            worker.append_banner(
                {
                    "type": "delta",
                    "title": "Context Update",
                    "sections": sections,
                    "is_delta": True,
                }
            )

    # ------------------------------------------------------------------
    #  State: sidebar / models
    # ------------------------------------------------------------------

    def _load_config_into_sidebar(self, chat_id: str) -> None:
        """Load a chat's saved skill/tool config into the sidebar.

        Args:
            chat_id: The chat id whose config to load.
        """
        stored = self.app.chat_store.load_chat(chat_id)
        if not stored:
            return
        config = stored.get("skills_config", {})
        activated = self._normalize_activated(config.get("activated", []) or [])
        tools = config.get("tools", {})
        self._loading_chat_config = True
        try:
            self._skill_model.apply_selection(activated)
            self._apply_tool_modes(tools)
        finally:
            self._loading_chat_config = False
        self._refresh_tool_model()
        self._update_config_chips()
        self._publish_config_summary(chat_id, config)

    def _publish_config_summary(self, chat_id: str, config: dict[str, Any]) -> None:
        """Publish a chat's skill/tool counts to its UI state and panel.

        Args:
            chat_id: The chat whose counts to publish.
            config: A ``{activated, tools}`` config dict.
        """
        if not chat_id:
            return
        tools = config.get("tools", {}) or {}
        state = self.session.state(chat_id)
        state.activated_count = len(config.get("activated", []) or [])
        state.allow_count = sum(1 for mode in tools.values() if mode == "allow")
        state.ask_count = sum(1 for mode in tools.values() if mode == "ask")
        state.block_count = sum(1 for mode in tools.values() if mode == "block")
        self.session.refresh_chat_panels(chat_id)

    def _rebuild_skill_sidebar(self) -> None:
        """Rebuild the skill tree and tool model from refreshed manager data.

        Preserves the current selections; selections for deleted skills are dropped.
        """
        self._skill_model.rebuild(self.app.skill_manager.get_skill_tree(), self._search_text)
        self._apply_tool_modes(self._tool_modes)
        self._refresh_tool_model()
        self.skills_changed.emit()

    def _refresh_tool_model(self) -> None:
        """Rebuild the tool model from the current selection and modes."""
        manager = self.app.skill_manager
        display_names = {p: manager.path_to_display_name(p) for p in manager.skill_paths}
        self._tool_model.rebuild(
            manager.all_tools,
            set(self._skill_model.collect_selected_activated()),
            self._tool_modes,
            display_names,
        )
        self.tool_modes_changed.emit()

    def _apply_tool_modes(self, modes: dict[str, str]) -> None:
        """Merge a mode mapping over the defaults for all discovered tools.

        Args:
            modes: Stored or preset tool-mode mapping.
        """
        defaults = self.app.skill_manager.default_tool_modes()
        self._tool_modes = {name: modes.get(name, "ask") for name in defaults}

    def _refresh_presets(self, *, emit: bool = True) -> None:
        """Reload preset names from the store.

        Args:
            emit: Whether to emit :attr:`presets_changed`.
        """
        self._preset_names = self.app.preset_store.list_presets()
        if emit:
            self.presets_changed.emit()

    # ------------------------------------------------------------------
    #  State: active config chips
    # ------------------------------------------------------------------

    def _update_config_chips(self) -> None:
        """Rebuild the active-config chip list from current selections."""
        config = self._collect_sidebar_config()
        activated = config["activated"]
        tools = config["tools"]
        chips: list[dict[str, str]] = [
            self._summary_chip(
                "Activated", len(activated), COLOR_CHIP_ACTIVATED_BG, COLOR_CHIP_ACTIVATED_FG
            ),
            self._summary_chip(
                "Allow",
                sum(1 for mode in tools.values() if mode == "allow"),
                COLOR_CHIP_ALLOW_BG,
                COLOR_CHIP_ALLOW_FG,
            ),
            self._summary_chip(
                "Ask",
                sum(1 for mode in tools.values() if mode == "ask"),
                COLOR_CHIP_ASK_BG,
                COLOR_CHIP_ASK_FG,
            ),
            self._summary_chip(
                "Block",
                sum(1 for mode in tools.values() if mode == "block"),
                COLOR_CHIP_BLOCK_BG,
                COLOR_CHIP_BLOCK_FG,
            ),
        ]
        for path in activated:
            chips.append(
                self._chip(self.app.skill_manager.path_to_display_name(path), *_CHIP_ACTIVATED)
            )
        for tool_name, mode in tools.items():
            bg, fg = _MODE_CHIP_COLORS.get(mode, _MODE_CHIP_COLORS["ask"])
            chips.append(self._chip(f"{tool_name} ({mode})", bg, fg))
        self._config_chips = chips
        self.config_changed.emit()

    @staticmethod
    def _summary_chip(label: str, count: int, bg: str, fg: str) -> dict[str, str]:
        """Build a summary chip such as ``"Activated: 3"``.

        Args:
            label: The chip label prefix.
            count: The chip count.
            bg: Background colour.
            fg: Foreground colour.

        Returns:
            A ``{"label", "bg", "fg"}`` chip dict.
        """
        return SkillController._chip(f"{label}: {count}", bg, fg)

    @staticmethod
    def _chip(label: str, bg: str, fg: str) -> dict[str, str]:
        """Build a config chip dict.

        Args:
            label: The chip text.
            bg: Background colour.
            fg: Foreground colour.

        Returns:
            A ``{"label", "bg", "fg"}`` chip dict.
        """
        return {"label": label, "bg": bg, "fg": fg}

    # ------------------------------------------------------------------
    #  Watcher
    # ------------------------------------------------------------------

    def _on_skill_files_changed(self) -> None:
        """Watchdog callback (background thread) — emit only, never touch models."""
        self.skill_files_changed.emit()

    @Slot()
    def _handle_skill_files_changed(self) -> None:
        """Refresh skill data after a watchdog event (runs on the GUI thread)."""
        logger.info("Skill files changed — scheduling refresh")
        self._spawn(self._refresh_skills())

    async def _refresh_skills(self) -> None:
        """Re-scan the skills directory off the loop, then rebuild the sidebar."""
        try:
            await asyncio.to_thread(self.app.skill_manager.refresh)
        except Exception as error:
            logger.error("Skill refresh failed: %s", error)
            self.toast_requested.emit("Failed to refresh skills.", TOAST_ERROR)
            return
        self._rebuild_skill_sidebar()
