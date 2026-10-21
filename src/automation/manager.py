"""Automation manager — discovers automations and tracks their run state.

An automation is any directory (at any depth) beneath ``automations_dir`` that
contains an ``AUTOMATION.py`` file.  The file starts with YAML frontmatter (name,
description, activation, schedule/event, optional skills) followed by Python code
documented with skill-like comments.

Enable/disable state and the last-run timestamp are kept in
``storage/automations.json`` so frontmatter stays read-only.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from pathlib import Path
import threading
from typing import Any

from croniter import croniter
import frontmatter
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..skill.models import ValidationIssue, ValidationLevel
from .models import ActivationType, AutomationInfo, parse_iso_date

logger = logging.getLogger("procoo_qt")


class AutomationManager:
    """Discovers automations and provides enable/disable and run-state tracking.

    Attributes:
        automations_dir: Filesystem path to the root automations directory.
        automations: List of discovered ``AutomationInfo`` objects.
    """

    def __init__(self, automations_dir: str, storage_dir: str) -> None:
        """Initialise the manager and discover automations from disk.

        Args:
            automations_dir: Root directory to scan for ``AUTOMATION.py`` files.
            storage_dir: Storage directory; state lives in ``automations.json``.
        """
        self.automations_dir = Path(automations_dir)
        self._state_path = Path(storage_dir) / "automations.json"
        self._state: dict[str, dict] = self._load_state()
        self._validation_issues: list[ValidationIssue] = []
        self._watcher_observer: Any | None = None
        self._watcher_thread: threading.Thread | None = None
        self._watcher_callback: Callable[[], None] | None = None
        self._watcher_timer: threading.Timer | None = None
        self._watcher_lock = threading.Lock()
        self._watcher_debounce_sec: float = 0.5

        self.automations: list[AutomationInfo] = self.discover_automations()
        self._by_path: dict[str, AutomationInfo] = {a.path: a for a in self.automations}

        self._print_validation()

    # ------------------------------------------------------------------
    #  Public: Discovery
    # ------------------------------------------------------------------

    def discover_automations(self) -> list[AutomationInfo]:
        """Recursively scan for ``AUTOMATION.py`` files.

        A valid automation is any directory (at any depth) containing an
        ``AUTOMATION.py`` file with parseable YAML frontmatter.

        Returns:
            List of ``AutomationInfo`` objects, one per discovered automation.
        """
        results: list[AutomationInfo] = []
        if not self.automations_dir.is_dir():
            return results

        for auto_file in sorted(self.automations_dir.rglob("AUTOMATION.py")):
            entry = auto_file.parent
            rel_path = str(entry.relative_to(self.automations_dir)).replace("\\", "/")
            info = self._load_automation_info(auto_file, entry, rel_path)
            if info is not None:
                results.append(info)

        return results

    def refresh(self) -> None:
        """Clear validation issues and re-discover automations from disk."""
        self._validation_issues.clear()
        self.automations = self.discover_automations()
        self._by_path = {a.path: a for a in self.automations}
        self._print_validation()

    # ------------------------------------------------------------------
    #  Public: Lookup
    # ------------------------------------------------------------------

    def get_automation(self, path: str) -> AutomationInfo | None:
        """Return an automation by its relative path, or ``None``."""
        return self._by_path.get(path)

    def get_event_automations(self, event: str) -> list[AutomationInfo]:
        """Return enabled event automations matching an event name (case-insensitive).

        Args:
            event: The incoming event name.

        Returns:
            Matching ``AutomationInfo`` objects (possibly empty).
        """
        wanted = event.strip().casefold()
        return [
            info
            for info in self.automations
            if info.activation == ActivationType.EVENT and info.event.strip().casefold() == wanted
        ]

    def scheduled_automations(self) -> list[AutomationInfo]:
        """Return all scheduled automations regardless of enabled state."""
        return [info for info in self.automations if info.activation == ActivationType.SCHEDULED]

    def get_validation_issues(self) -> list[ValidationIssue]:
        """Return all validation issues collected during discovery."""
        return list(self._validation_issues)

    # ------------------------------------------------------------------
    #  Public: State (enabled / last run)
    # ------------------------------------------------------------------

    def is_enabled(self, path: str) -> bool:
        """Return whether an automation is enabled (default ``True``)."""
        return bool(self._state.get(path, {}).get("enabled", True))

    def set_enabled(self, path: str, enabled: bool) -> None:
        """Persist an automation's enabled state and update the in-memory model.

        Args:
            path: Relative automation path.
            enabled: The new enabled state.
        """
        record = self._state.setdefault(path, {})
        record["enabled"] = bool(enabled)
        self._save_state()
        info = self._by_path.get(path)
        if info is not None:
            info.enabled = bool(enabled)
        logger.info("Automation '%s' %s", path, "enabled" if enabled else "disabled")

    def record_run(self, path: str, timestamp: str) -> None:
        """Persist the last-run timestamp for an automation.

        Args:
            path: Relative automation path.
            timestamp: Completion timestamp string.
        """
        record = self._state.setdefault(path, {})
        record["last_run"] = timestamp
        self._save_state()
        info = self._by_path.get(path)
        if info is not None:
            info.last_run = timestamp

    # ------------------------------------------------------------------
    #  Private: Loading
    # ------------------------------------------------------------------

    def _load_automation_info(
        self, auto_file: Path, entry: Path, rel_path: str
    ) -> AutomationInfo | None:
        """Parse and validate a single ``AUTOMATION.py`` into an ``AutomationInfo``.

        Args:
            auto_file: Absolute path to the ``AUTOMATION.py`` file.
            entry: The automation directory.
            rel_path: Path relative to ``automations_dir``.

        Returns:
            The parsed automation, or ``None`` when required fields are invalid.
        """
        source = f"automation:{rel_path}"
        try:
            with open(auto_file, encoding="utf-8") as f:
                post = frontmatter.load(f)
        except Exception as e:
            logger.error("Failed to parse AUTOMATION.py for '%s': %s", rel_path, e)
            self._add_issue(
                ValidationLevel.ERROR,
                source,
                "Failed to parse AUTOMATION.py frontmatter — file may be malformed.",
                "",
            )
            return None

        metadata = post.metadata
        missing_required = False

        name = str(metadata.get("name", entry.name))
        if not metadata.get("name"):
            self._add_issue(ValidationLevel.ERROR, source, "Missing 'name' frontmatter.", "name")
            missing_required = True

        description = str(metadata.get("description", ""))
        if not metadata.get("description") or not description.strip():
            self._add_issue(
                ValidationLevel.ERROR, source, "Missing or empty 'description'.", "description"
            )
            missing_required = True

        activation_raw = str(metadata.get("activation", "")).strip().lower()
        activation: ActivationType | None = None
        if activation_raw not in (ActivationType.SCHEDULED, ActivationType.EVENT):
            self._add_issue(
                ValidationLevel.ERROR,
                source,
                "Missing or invalid 'activation' (expected 'scheduled' or 'event').",
                "activation",
            )
            missing_required = True
        else:
            activation = ActivationType(activation_raw)

        schedule = str(metadata.get("schedule", "")).strip()
        event = str(metadata.get("event", "")).strip()

        if activation == ActivationType.SCHEDULED:
            if not schedule:
                self._add_issue(
                    ValidationLevel.ERROR,
                    source,
                    "Scheduled automation requires a 'schedule' cron expression.",
                    "schedule",
                )
                missing_required = True
            elif not croniter.is_valid(schedule):
                self._add_issue(
                    ValidationLevel.ERROR,
                    source,
                    f"Invalid cron expression: '{schedule}'.",
                    "schedule",
                )
                missing_required = True
        elif activation == ActivationType.EVENT and not event:
            self._add_issue(
                ValidationLevel.ERROR,
                source,
                "Event automation requires a non-empty 'event' name.",
                "event",
            )
            missing_required = True

        if not (post.content or "").strip():
            self._add_issue(
                ValidationLevel.WARNING,
                source,
                "AUTOMATION.py has no code body.",
                "body",
            )

        start_date, end_date = self._load_window_dates(metadata, source)

        if missing_required or activation is None:
            return None

        activated_skills = self._string_list(
            metadata.get("activated_skills", metadata.get("primary_skills"))
        )

        has_scripts = (entry / "scripts").is_dir()
        if has_scripts and not any(
            f.name.endswith(".py") for f in (entry / "scripts").iterdir() if f.is_file()
        ):
            self._add_issue(
                ValidationLevel.WARNING,
                source,
                "scripts/ directory contains no .py files.",
                "scripts",
            )
        has_references = (entry / "references").is_dir()

        return AutomationInfo(
            name=name,
            path=rel_path,
            directory=str(entry.resolve()),
            description=description,
            activation=activation,
            schedule=schedule,
            event=event,
            activated_skills=activated_skills,
            has_scripts=has_scripts,
            has_references=has_references,
            enabled=self.is_enabled(rel_path),
            last_run=str(self._state.get(rel_path, {}).get("last_run", "")),
            start_date=start_date,
            end_date=end_date,
        )

    def _load_window_dates(self, metadata: dict, source: str) -> tuple[str, str]:
        """Extract the optional ``start_date`` / ``end_date`` frontmatter window.

        Malformed values produce a validation warning and are ignored (treated
        as unset) so a typo cannot silently block an automation forever.

        Args:
            metadata: The parsed YAML frontmatter mapping.
            source: Source label used for validation issues.

        Returns:
            A ``(start_date, end_date)`` tuple of normalised ``YYYY-MM-DD``
            strings, either of which may be empty.
        """
        normalised: list[str] = []
        for field in ("start_date", "end_date"):
            raw = str(metadata.get(field, "")).strip()
            parsed = parse_iso_date(raw)
            if raw and parsed is None:
                self._add_issue(
                    ValidationLevel.WARNING,
                    source,
                    f"Invalid '{field}' (expected 'YYYY-MM-DD'): '{raw}'.",
                    field,
                )
                normalised.append("")
            else:
                normalised.append("" if parsed is None else parsed.isoformat())
        return normalised[0], normalised[1]

    # ------------------------------------------------------------------
    #  Private: State storage
    # ------------------------------------------------------------------

    def _load_state(self) -> dict[str, dict]:
        """Load the per-automation state map from ``automations.json``."""
        if not self._state_path.is_file():
            return {}
        try:
            with open(self._state_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to read automation state: %s", e)
            return {}
        automations = data.get("automations", {}) if isinstance(data, dict) else {}
        return automations if isinstance(automations, dict) else {}

    def _save_state(self) -> None:
        """Atomically persist the per-automation state map."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.parent / (self._state_path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"automations": self._state}, f, indent=2)
            tmp.replace(self._state_path)
        except OSError as e:
            logger.error("Failed to write automation state: %s", e)

    # ------------------------------------------------------------------
    #  Public: Watching
    # ------------------------------------------------------------------

    def start_watching(self, callback: Callable[[], None]) -> None:
        """Watch the automations directory for changes (debounced).

        Uses ``watchdog`` on a background thread.  The *callback* is invoked on
        that thread after a debounce period; the caller must marshal to the UI
        thread (e.g. by emitting a Qt signal).

        Args:
            callback: Zero-argument callable invoked when automations change.
        """
        if self._watcher_observer is not None:
            return

        self._watcher_callback = callback

        class _AutomationDirEventHandler(FileSystemEventHandler):
            """Debounced event handler — resets the timer on each event."""

            def __init__(self, mgr: AutomationManager) -> None:
                super().__init__()
                self._mgr = mgr

            def on_any_event(self, event) -> None:
                self._mgr._schedule_refresh()

        event_handler = _AutomationDirEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.automations_dir), recursive=True)

        self._watcher_observer = observer

        def _run_observer() -> None:
            observer.start()
            try:
                while observer.is_alive():
                    observer.join(1)
            except (KeyboardInterrupt, SystemExit):
                pass

        self._watcher_thread = threading.Thread(target=_run_observer, daemon=True)
        self._watcher_thread.start()

    def stop_watching(self) -> None:
        """Stop the automations directory watcher and clean up threads / timers."""
        if self._watcher_observer is None:
            return

        with self._watcher_lock:
            if self._watcher_timer is not None:
                self._watcher_timer.cancel()
                self._watcher_timer = None

        observer = self._watcher_observer
        observer.stop()
        observer.join(timeout=2)

        self._watcher_observer = None
        self._watcher_thread = None
        self._watcher_callback = None

    def _schedule_refresh(self) -> None:
        """Schedule a debounced refresh when a file change is detected."""
        with self._watcher_lock:
            if self._watcher_timer is not None:
                self._watcher_timer.cancel()
            self._watcher_timer = threading.Timer(
                self._watcher_debounce_sec,
                self._on_watcher_debounced,
            )
            self._watcher_timer.start()

    def _on_watcher_debounced(self) -> None:
        """Invoke the user callback after a debounce period."""
        cb = self._watcher_callback
        if cb is not None:
            cb()

    # ------------------------------------------------------------------
    #  Private: Validation
    # ------------------------------------------------------------------

    def _add_issue(self, level: ValidationLevel, source: str, message: str, field: str) -> None:
        """Append a validation issue to the collection."""
        self._validation_issues.append(
            ValidationIssue(level=level, source=source, message=message, field=field)
        )

    def _print_validation(self) -> None:
        """Log a validation summary with severity-tagged lines."""
        if not self._validation_issues:
            return
        errors = [i for i in self._validation_issues if i.level == ValidationLevel.ERROR]
        warnings = [i for i in self._validation_issues if i.level == ValidationLevel.WARNING]

        logger.info("=== Automation Validation Report ===")
        for issue in self._validation_issues:
            tag = issue.level.value.upper()
            extra = f" ({issue.field})" if issue.field else ""
            if issue.level == ValidationLevel.ERROR:
                logger.error("  [%s] %s%s: %s", tag, issue.source, extra, issue.message)
            else:
                logger.warning("  [%s] %s%s: %s", tag, issue.source, extra, issue.message)
        logger.info("--- %d error(s), %d warning(s) ---", len(errors), len(warnings))

    # ------------------------------------------------------------------
    #  Private: Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        """Coerce a frontmatter value into a list of non-empty strings.

        Args:
            value: A list, single string, or ``None`` from frontmatter.

        Returns:
            A list of stripped strings (empty when *value* is missing).
        """
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []
