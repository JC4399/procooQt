Use typing. Write google-style docstring. Add section divider if necessary.
Ruff and ty (`ty check`) is used for this project. Make sure to use them for quality checking. DO NOT use mypy or pyright.

Chat memory: `session.messages` is the single source of truth — an OpenAI-compatible list
`[{role,content,tool_calls,...}]` with `_`-prefixed metadata (`_thinking`, `_mode`). The UI renders
from it directly; the formatter strips `_` keys when sending to the LLM. QML models are derived from
`session.messages`, never a second source of truth.

# Code Style Guide

## Imports

- Three groups, separated by blank lines: **stdlib** → **third-party** → **local** (relative).
- Sort alphabetically within each group (enforced by ruff `I`).
- Use `from .module import Name` and `from ..parent import Name` — never absolute `src.` imports.
- Lazy imports (inside functions/methods) are OK for circular-dependency avoidance.
- Always include `from __future__ import annotations` in every file so all annotations are stringified.

## Type Annotations

- Annotate every function signature — parameters and return type.
- Always annotate `__init__` with `-> None`.
- Use `X | None`, not `Optional[X]`.
- Use `list[dict]`, not `List[Dict]`.

## TYPE_CHECKING Pattern

- Controller classes **must** declare cross-controller attributes in an `if TYPE_CHECKING:` block at class body top.
- Stub methods inside TYPE_CHECKING end with `...` (bare ellipsis).
- Always pair TYPE_CHECKING with `from __future__ import annotations`.

## Docstrings

- **Google-style** everywhere.
- Every public class, method, and function must have a docstring.
- Every `__init__.py` (package) must have a module-level docstring.
- Sections: `Args:`, `Returns:`, `Yields:`, `Raises:`, `Attributes:`.

## Quoting

- Double quotes for all strings.
- Use Python auto-escaping when mixing with `'` to avoid `\"` noise.

## Naming

| Kind | Convention | Example |
|---|---|---|
| Files | `snake_case` | `chat_controller.py` |
| QML files | `PascalCase` | `ChatPanel.qml` |
| Variables | `snake_case` | `session_id` |
| Functions / methods | `snake_case` | `_build_center()` |
| Classes | `PascalCase` | `ChatController` |
| QML ids | `camelCase` | `id: messageList` |
| Module-level constants | `UPPER_CASE` | `COLOR_PAGE_BG` |
| Private members | `_prefix` | `_tool_config` |
| "Truly private" (mangling) | `__prefix` | Not used |

## Logger

- Module-level: `logger = logging.getLogger("procoo_qt")`.
- Use f-string formatting: `logger.info("Session %s created", session_id)`.

## Section Dividers

Use the 66-character dashed line between logical sections inside a file:

```python
# ------------------------------------------------------------------
#  Section name
# ------------------------------------------------------------------
```

## Line Length

- 100 characters (enforced by ruff).

## Error Handling

- Use the project exception hierarchy: `ProcooError` → `ConfigError`, `AgentError`, `ToolError`, `SessionError`.
- Always provide `brief` (UI-visible) and `detail` (log-visible) messages.

# Qt Controller Template

All controller classes under `src/qt/` follow this uniform structure. **Use composition, not
multiple inheritance** — `ProcooQtUI` owns one instance of each controller; controllers never inherit
from each other. A class may inherit from exactly one `QObject` subclass.

```python
"""File-level docstring — one sentence describing the controller."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger("procoo_qt")


class SessionController(QObject):
    """Class-level docstring — one sentence describing the controller's role."""

    # Signals first, with their payload types.
    sessions_changed = Signal()

    if TYPE_CHECKING:
        # Attributes provided by ui.py orchestrator
        app: Any
        engine: Any

        # Attributes owned by this controller
        session_model: SessionListModel

        # Attributes provided by other controllers (composition)
        chat: ChatController

        # Cross-controller method stubs (alphabetical, uniform signatures)
        def _handle_send(self, text: str) -> None: ...

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def __init__(self, app: Any, parent: QObject | None = None) -> None:
        """Initialise the controller.

        Args:
            app: The top-level ``ProcooApp`` holding the backend subsystems.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.app = app

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the controller's models and wire signals."""

    # ------------------------------------------------------------------
    #  Slot: <descriptive action name>
    # ------------------------------------------------------------------

    @Slot()
    def _handle_send(self) -> None:
        """Slot docstring."""
```

Rules:
- **Composition over inheritance**: one orchestrator, N controllers, no multiple inheritance.
- **Signals** are class attributes with typed payloads (`Signal(str)`, `Signal(int, str)`), declared before `__init__`.
- **Slots** use the `@Slot(...)` decorator with argument types; name them `_handle_<action>`.
- **QML boundary**: anything QML touches is a `Signal`, `Slot`, or `Property`. Never expose raw backend objects.
- **SECTION → METHOD**: every method or tightly-related method pair gets its own section divider.
- **Ordering**: signals → TYPE_CHECKING → `__init__` → Builder(s) → State → Slots → Helpers.
- **Slot sections** are prefixed `Slot: <action>` (e.g. `Slot: Send`, `Slot: Save preset`).
- **TYPE_CHECKING attributes** grouped by origin: ui.py → this controller → other controllers.
- **`@staticmethod`** only when a method is genuinely stateless and needs no class/instance state.
- All methods annotated with return type, including `-> None`.

# QML Conventions

- **View-only**: QML components contain no business logic. They bind to model roles and call controller slots; they never import Python.
- One QML file per visual unit, `PascalCase`, placed under `qml/panels/`, `qml/cards/`, or `qml/components/`.
- **Flat square style**: `radius: 0` and explicit `border.color` / `border.width` on every surface. Start from the `Basic` Qt Quick Controls style (`QQuickStyle.setStyle("Basic")`); do not use Material.
- All colours, font sizes, and spacing come from the `Theme` context property (`Theme.colors.pageBg`, `Theme.metrics.cardRadius`, `Theme.fontMono`). Never hard-code a hex colour in QML.
- A component exposes state via `property`/`property alias`; parent components pass data in, children emit signals up. No imperative drilling.
- Model roles use an `IntEnum` in Python exposed to QML (`Roles.kind`, `Roles.bodyHtml`, …). QML delegates switch on the role.
- Selectable long text uses `TextEdit { readOnly: true; textFormat: TextEdit.RichText }`, not `Text`.
- Resizable regions use `SplitView`; do not hand-roll drag-resize handles.
- Collapsible cards animate `implicitHeight`/`visible` via QML states and `NumberAnimation`.
- Status pulses use a QML `SequentialAnimation` on `opacity`; do not drive them from Python timers.

# Package `__init__.py`

- Every package directory under `src/` must contain an `__init__.py` with a one-line docstring describing the package.

# Non-UI Code (`config/`, `session/`, `skill/`, `util/`)

- **Class docstrings**: Every class must have one. Include `Attributes:` when the class has public state.
- **Method return types**: All methods must be annotated with return type.
- **Section dividers**: Use the standard 66-char `-` divider (same as controllers). Apply in any class with 5+ methods; group logically with `Public:` / `Private:` prefix.
- **Module-level init**: Heavy side-effects (e.g. `sys.exit()`, network calls) must be inside `if __name__` guard. Singleton creation at module level is acceptable.
- **Structural twins**: Classes with similar roles (e.g. JSON CRUD stores) must follow the same internal structure — same divider placement, same method order.

# Concurrency

- The app runs **one asyncio event loop fused with Qt** via `qasync.QEventLoop`. There is exactly one loop, on the GUI thread.
- Async work is scheduled with `asyncio.ensure_future(...)`; never `page.run_task` (Flet-only).
- Because everything runs on the GUI thread, controllers may update models and properties directly from `async` slots. No locks.
- **Never block the loop**: wrap synchronous file I/O (`SessionStore`, large skill scans) in `await asyncio.to_thread(...)`.
- Tool subprocesses use `asyncio.create_subprocess_exec` inside `asyncio.gather` — do not use `QProcess`.
- The `watchdog` observer callback runs on a background thread. It must only **emit a Qt `Signal`**; the connected slot then runs queued on the GUI thread. Never touch models from the watcher thread.

# DRY: No Copy-Paste

- If a pattern appears **3+ times**, factor it into a helper function or parametrized method.
- **Sidebar config**: Use a single `_collect_selected_skills()` and `_collect_tool_modes()` — never inline the checkbox/radio iteration.
- **Resize**: Use `SplitView` rather than per-panel resize handlers.
- **Token counting**: One `count_messages_by_role(messages)` function for all for-loop token enumeration.
- **Rebuild vs Build**: `_rebuild_*` methods must reuse `_build_*` logic, never duplicate subtree construction.

# Method Length

- Methods should stay under **70 lines**. Split longer methods into sub-methods named after their logical phase (e.g. `_compute_render_keys`, `_build_suffix_items`).
- Monolithic event-loop methods (e.g. `_run_chat_loop`) must be split into distinct phases: hydrate, consume-events, cleanup.

# State Objects

- Group related mutable tracking fields into **sub-dataclasses** rather than flat fields on `SessionState`. For example, thinking+response pending card state belongs in a `StreamingCardState`.
- Avoid `_last_rendered_*` / `_last_tok_counted_*` prefix sprawl — put those in the sub-dataclass they track.

# Chat Item Builders (`chat_items.py`)

- All card/item builders must use shared base helpers for the repeated pattern: header row → token display → body → collapsible flag. Never inline a header row.
- **Pending cards** must inherit header styling from their non-pending counterpart via the shared base — never copy-paste the header.
- Builders return **plain role dicts** (or dataclasses) consumed by `ChatListModel`; they never touch QML objects.

# Logger

- Always `import logging` at module top level. Never use `__import__("logging")` or lazy imports for the logger module.
- Module-level: `logger = logging.getLogger("procoo_qt")`.
