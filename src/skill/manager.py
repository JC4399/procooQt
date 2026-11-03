"""Skill manager — discovers, loads, and manages skills and their tools."""

from __future__ import annotations

import ast
from collections.abc import Callable
import logging
import os
from pathlib import Path
import threading
from typing import Any

import frontmatter
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .models import SkillContent, SkillInfo, ToolInfo, ValidationIssue, ValidationLevel

logger = logging.getLogger("procoo_qt")


class SkillManager:
    """Discovers skills, loads their content and tools, and provides a unified
    management interface.

    Supports nested skill directories. Skills are identified by their relative
    path from ``skills_dir`` (e.g. ``"coding/python"``).

    Attributes:
        skills_dir: Filesystem path to the root skills directory.
        skills: List of discovered ``SkillInfo`` objects.
        skill_paths: List of discovered skill relative paths.
        all_tools: List of all discovered ``ToolInfo`` objects.
        tool_names: List of all discovered tool names.
    """

    def __init__(self, skills_dir: str) -> None:
        self.skills_dir = Path(skills_dir)
        self._tool_cache: dict[str, list[ToolInfo]] = {}
        self._schema_cache: dict[str, dict] = {}
        self._content_cache: dict[str, tuple[float, SkillContent]] = {}
        self._validation_issues: list[ValidationIssue] = []
        self._watcher_observer: Any | None = None
        self._watcher_thread: threading.Thread | None = None
        self._watcher_callbacks: list[Callable[[], None]] = []
        self._watcher_timer: threading.Timer | None = None
        self._watcher_lock = threading.Lock()
        self._watcher_debounce_sec: float = 0.5

        self.skills: list[SkillInfo] = self.discover_skills()
        self.skill_paths: list[str] = [s.path for s in self.skills]
        self._skill_by_path: dict[str, SkillInfo] = {s.path: s for s in self.skills}
        self.all_tools: list[ToolInfo] = self.scan_all_tools()
        self.tool_names: list[str] = [t.name for t in self.all_tools]

        self._validate_cross_checks()
        self._print_validation()

    # ------------------------------------------------------------------
    #  Public: Discovery
    # ------------------------------------------------------------------

    def discover_skills(self) -> list[SkillInfo]:
        """Recursively scan the skills directory for ``SKILL.md`` files.

        A valid skill is any directory (at any depth) containing a
        ``SKILL.md`` file with YAML frontmatter.  Directories without a
        ``SKILL.md`` are treated as grouping folders.

        Returns:
            List of ``SkillInfo`` objects, one per discovered skill.
        """
        results: list[SkillInfo] = []
        if not self.skills_dir.is_dir():
            return results

        for skill_md in sorted(self.skills_dir.rglob("SKILL.md")):
            entry = skill_md.parent
            rel_path = entry.relative_to(self.skills_dir).as_posix()
            if rel_path == ".":
                rel_path = os.path.basename(str(self.skills_dir))

            try:
                with open(skill_md, encoding="utf-8") as f:
                    post = frontmatter.load(f)
            except Exception as e:
                logger.error("Failed to parse SKILL.md for skill '%s': %s", rel_path, e)
                self._add_issue(
                    ValidationLevel.ERROR,
                    f"skill:{rel_path}",
                    "Failed to parse SKILL.md frontmatter — file may be malformed.",
                    "",
                )
                continue

            name = str(post.metadata.get("name", entry.name))
            description = str(post.metadata.get("description", ""))
            instructions = post.content.strip() if post.content else ""

            source = f"skill:{rel_path}"

            missing_required = False

            if not post.metadata.get("name"):
                self._add_issue(
                    ValidationLevel.ERROR,
                    source,
                    "Missing 'name' in SKILL.md frontmatter — required.",
                    "name",
                )
                missing_required = True
            if not post.metadata.get("description"):
                self._add_issue(
                    ValidationLevel.ERROR,
                    source,
                    "Missing 'description' in SKILL.md frontmatter — required.",
                    "description",
                )
                missing_required = True
            elif not description.strip():
                self._add_issue(
                    ValidationLevel.ERROR,
                    source,
                    "SKILL.md description field is empty.",
                    "description",
                )
                missing_required = True

            if not instructions:
                self._add_issue(
                    ValidationLevel.ERROR,
                    source,
                    "SKILL.md body (instructions) is empty — required.",
                    "instructions",
                )
                missing_required = True

            if missing_required:
                continue

            has_tools = (entry / "scripts").is_dir()
            if has_tools:
                has_tool_files = any(
                    f.name.endswith(".py") and not f.name.startswith("_")
                    for f in (entry / "scripts").iterdir()
                )
                if not has_tool_files:
                    self._add_issue(
                        ValidationLevel.WARNING,
                        source,
                        "scripts/ directory exists but contains no valid .py script files.",
                        "has_tools",
                    )

            results.append(
                SkillInfo(
                    name=name,
                    path=rel_path,
                    description=description,
                    has_tools=has_tools,
                )
            )

        return results

    # ------------------------------------------------------------------
    #  Public: Skill loading
    # ------------------------------------------------------------------

    def load_skill_content(self, skill_path: str) -> SkillContent | None:
        """Load the full content of a skill by its relative path.

        Args:
            skill_path: Skill relative path from skills_dir (e.g. ``"coding/python"``).

        Returns:
            ``SkillContent`` if found, or ``None``.
        """
        entry = self._resolve_skill_path(skill_path)
        if entry is None:
            return None

        skill_md = entry / "SKILL.md"

        try:
            mtime = skill_md.stat().st_mtime
        except OSError as e:
            logger.error("Failed to stat SKILL.md for skill '%s': %s", skill_path, e)
            return None
        cached = self._content_cache.get(skill_path)
        if cached is not None and cached[0] == mtime:
            return cached[1]

        try:
            with open(skill_md, encoding="utf-8") as f:
                post = frontmatter.load(f)
        except Exception as e:
            logger.error("Failed to load SKILL.md for skill '%s': %s", skill_path, e)
            return None

        name = str(post.metadata.get("name", entry.name))
        description = str(post.metadata.get("description", ""))
        instructions = post.content.strip()

        scripts_dir = entry / "scripts"
        scripts = sorted([p.name for p in scripts_dir.iterdir()]) if scripts_dir.is_dir() else []

        content = SkillContent(
            name=name,
            path=skill_path,
            description=description,
            instructions=instructions,
            scripts=scripts,
        )
        self._content_cache[skill_path] = (mtime, content)
        return content

    def load_skill_contents(self, skill_paths: list[str]) -> list[dict]:
        """Load full content for a list of skill paths.

        Args:
            skill_paths: Skill relative paths to load.

        Returns:
            List of skill-content dicts (from ``SkillContent.model_dump()``).
        """
        contents = []
        for path in skill_paths:
            content = self.load_skill_content(self.normalize_skill_path(path))
            if content:
                contents.append(content.model_dump())
        return contents

    # ------------------------------------------------------------------
    #  Public: Tool scanning
    # ------------------------------------------------------------------

    def scan_tools(self, skill_path: str) -> list[ToolInfo]:
        """Discover tool modules inside a skill's ``scripts/`` directory.

        Results are cached per skill path.

        Args:
            skill_path: Skill relative path whose tools should be scanned.

        Returns:
            List of ``ToolInfo`` objects (empty if no tools found).
        """
        if skill_path in self._tool_cache:
            return self._tool_cache[skill_path]

        tools: list[ToolInfo] = []
        skill_dir = self._resolve_skill_path(skill_path)
        if skill_dir is None:
            return tools

        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            return tools

        for f in sorted(scripts_dir.iterdir()):
            if not f.name.endswith(".py") or f.name.startswith("_"):
                continue
            filepath_str = str(f)
            tool_name = f.name[:-3]
            tools.append(
                ToolInfo(
                    name=tool_name,
                    skill_path=skill_path,
                    description="",
                    filepath=filepath_str,
                )
            )

        self._tool_cache[skill_path] = tools
        return tools

    def scan_all_tools(self) -> list[ToolInfo]:
        """Scan all discovered skills and return a combined list of tools."""
        all_tools: list[ToolInfo] = []
        for skill in self.skills:
            all_tools.extend(self.scan_tools(skill.path))
        return all_tools

    # ------------------------------------------------------------------
    #  Public: Tool loading
    # ------------------------------------------------------------------

    def load_tool_functions(self, selected_skills: list[str]) -> list[dict]:
        """Build tool-definition dicts for the given skill paths.

        Tool descriptions and parameter schemas are inferred from the
        ``run()`` function's docstring and type annotations in each
        ``.py`` script via AST parsing.

        Args:
            selected_skills: Skill paths whose tools should be loaded.

        Returns:
            List of tool-definition dicts with keys: ``name``,
            ``description``, ``parameters``, ``script_path``,
            ``skill_path``, ``type``.
        """
        definitions: list[dict] = []
        for skill_path in selected_skills:
            for tool_info in self.scan_tools(self.normalize_skill_path(skill_path)):
                definitions.append(self._build_tool_definition(tool_info))
        return definitions

    def load_tool_functions_by_name(self, names: list[str]) -> list[dict]:
        """Build tool-definition dicts for explicit tool names.

        Searches every discovered skill.  Duplicate tool names resolve to the
        first discovered definition, with a warning, because the agent registry
        is keyed by name.

        Args:
            names: Tool names to load (order preserved, duplicates ignored).

        Returns:
            List of tool-definition dicts for the names that were found.
        """
        by_name: dict[str, ToolInfo] = {}
        for tool_info in self.all_tools:
            if tool_info.name in by_name:
                logger.warning(
                    "Duplicate tool name '%s' in '%s' and '%s'; using the first.",
                    tool_info.name,
                    by_name[tool_info.name].skill_path,
                    tool_info.skill_path,
                )
                continue
            by_name[tool_info.name] = tool_info

        definitions: list[dict] = []
        seen: set[str] = set()
        for name in names:
            tool_info = by_name.get(name)
            if tool_info is None or name in seen:
                continue
            seen.add(name)
            definitions.append(self._build_tool_definition(tool_info))
        return definitions

    def _build_tool_definition(self, tool_info: ToolInfo) -> dict:
        """Build one OpenAI-compatible tool definition from a discovered tool.

        Args:
            tool_info: The discovered tool metadata.

        Returns:
            A tool-definition dict with name, description, schema, and path.
        """
        schema = self._infer_tool_schema(tool_info.filepath, tool_info.name)
        return {
            "name": tool_info.name,
            "description": schema.get("description", ""),
            "parameters": schema.get(
                "parameters",
                {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            "script_path": tool_info.filepath,
            "skill_path": tool_info.skill_path,
            "type": "python" if tool_info.filepath.endswith(".py") else "unknown",
        }

    # ------------------------------------------------------------------
    #  Private: Schema inference (AST)
    # ------------------------------------------------------------------

    _TYPE_MAP: dict[str, str] = {  # noqa: RUF012
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
        "Any": "string",
    }

    def _infer_tool_schema(self, script_path: str, tool_name: str) -> dict:
        """Infer a JSON Schema tool definition from a Python script via AST.

        Parses the ``run()`` function's docstring (first paragraph = description,
        ``Args:`` section = parameter descriptions) and type annotations.

        Results are cached per script path.

        Args:
            script_path: Absolute path to the ``.py`` file.
            tool_name: Name of the tool (for warnings).

        Returns:
            Dict with ``description`` and ``parameters`` keys suitable for
            an OpenAI-compatible tool definition.
        """
        if script_path in self._schema_cache:
            return self._schema_cache[script_path]

        default_schema = {
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }

        try:
            with open(script_path, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=script_path)
        except (SyntaxError, OSError) as e:
            logger.warning("Failed to parse '%s' for schema inference: %s", script_path, e)
            self._schema_cache[script_path] = default_schema
            return default_schema

        func = self._find_run_function(tree)
        if func is None:
            logger.warning("No run() function found in '%s' — using empty schema.", script_path)
            self._schema_cache[script_path] = default_schema
            return default_schema

        docstring = ast.get_docstring(func) or ""
        param_docs = self._parse_google_docstring(docstring)
        description = param_docs.pop("", "")

        properties: dict[str, object] = {}
        required: list[str] = []

        for arg in func.args.args:
            if arg.arg == "self":
                continue
            prop: dict[str, object] = {}
            if arg.annotation is not None:
                prop = self._ast_type_to_json_schema(arg.annotation, arg.arg)

            if param_docs.get(arg.arg):
                prop["description"] = param_docs[arg.arg]

            has_default = self._arg_has_default(arg, func)
            if not has_default:
                required.append(arg.arg)

            properties[arg.arg] = prop

        schema = {
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
        self._schema_cache[script_path] = schema
        return schema

    @staticmethod
    def _find_run_function(
        tree: ast.Module,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """Find the top-level ``run`` (or ``async def run``) function in an AST.

        Args:
            tree: Parsed module AST.

        Returns:
            The ``FunctionDef`` / ``AsyncFunctionDef`` node, or ``None``.
        """
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run":
                return node
        return None

    @staticmethod
    def _arg_has_default(arg: ast.arg, func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check whether a function argument has a default value.

        Args:
            arg: The argument node to check.
            func: The parent function node.

        Returns:
            ``True`` if the argument has a default value.
        """
        defaults = func.args.defaults or []
        num_no_default = len(func.args.args) - len(defaults)
        for i, a in enumerate(func.args.args):
            if a.arg == arg.arg:
                return i >= num_no_default
        return False

    def _ast_type_to_json_schema(self, node: ast.expr, param_name: str) -> dict:
        """Convert an AST type annotation node to a JSON Schema property dict.

        Handles common patterns:
            - Simple types: ``str``, ``int``, ``float``, ``bool``
            - Generics: ``list[str]``, ``dict``
            - Unions: ``str | None``, ``Optional[str]``

        Args:
            node: AST expression node for the type annotation.
            param_name: Parameter name (for warnings).

        Returns:
            JSON Schema property dict with at least a ``"type"`` key.
        """
        json_type = self._resolve_ast_type(node, param_name)
        if json_type is None:
            return {"type": "string"}

        if json_type == "array":
            items_type = "string"
            if isinstance(node, ast.Subscript):
                inner = self._resolve_ast_type(node.slice, param_name)
                if inner:
                    items_type = inner
            return {"type": "array", "items": {"type": items_type}}
        return {"type": json_type}

    def _resolve_ast_type(self, node: ast.expr, param_name: str) -> str | None:
        """Recursively resolve an AST type node to a JSON Schema type string.

        Args:
            node: AST expression node.
            param_name: Parameter name (for warnings).

        Returns:
            A JSON Schema type string (``"string"``, ``"integer"``,
            ``"number"``, ``"boolean"``, ``"array"``, ``"object"``), or
            ``None`` for unannotated / unknown types.
        """
        if isinstance(node, ast.Name):
            if node.id in self._TYPE_MAP:
                return self._TYPE_MAP[node.id]
            logger.warning(
                "Unrecognised type annotation '%s' for param '%s' — defaulting to string.",
                node.id,
                param_name,
            )
            return "string"

        if isinstance(node, ast.Subscript):
            base_type = self._resolve_ast_type(node.value, param_name)
            if base_type == "array":
                self._resolve_ast_type(node.slice, param_name)
                return "array"
            if base_type == "object":
                return "object"
            logger.warning(
                "Unrecognised subscript annotation for param '%s' — defaulting to string.",
                param_name,
            )
            return "string"

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left = self._resolve_ast_type(node.left, param_name)
            if isinstance(node.right, ast.Constant) and node.right.value is None:
                return left
            right = self._resolve_ast_type(node.right, param_name)
            return left or right

        if isinstance(node, ast.Constant) and node.value is None:
            return None

        logger.warning(
            "Unrecognised type annotation for param '%s' — defaulting to string.",
            param_name,
        )
        return "string"

    @staticmethod
    def _parse_google_docstring(docstring: str) -> dict[str, str]:
        """Parse a Google-style docstring into description + parameter docs.

        The first paragraph (up to ``Args:``, ``Returns:``, or a blank line)
        is treated as the tool description (key ``""``).  The ``Args:``
        section is parsed as ``param_name: description text`` lines.

        Args:
            docstring: Raw docstring text (with or without leading
                whitespace — lines are dedented).

        Returns:
            Dict mapping ``""`` → description and ``param_name`` →
            description string for each documented parameter.
        """
        import textwrap

        dedented = textwrap.dedent(docstring)
        paragraphs = dedented.split("\n\n")
        result: dict[str, str] = {"": ""}
        if not paragraphs:
            return result

        first = paragraphs[0].strip()
        if first and not first.startswith(("Args:", "Returns:", "Raises:", "Yields:")):
            result[""] = first

        args_text = None
        for para in paragraphs:
            stripped = para.strip()
            if stripped.startswith("Args:"):
                args_text = stripped
                break

        if args_text is None:
            return result

        lines = args_text.split("\n")
        body = textwrap.dedent("\n".join(lines[1:]))
        current_param: str | None = None
        current_desc: list[str] = []

        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            if not line[0].isspace():
                if current_param is not None:
                    result[current_param] = " ".join(current_desc)
                    current_desc = []
                if ":" in stripped:
                    current_param, desc = stripped.split(":", 1)
                    current_param = current_param.strip()
                    current_desc = [desc.strip()] if desc.strip() else []
                else:
                    current_param = None
            else:
                if current_param is not None and stripped:
                    current_desc.append(stripped)

        if current_param is not None:
            result[current_param] = " ".join(current_desc)

        return result

    def build_tool_config(
        self, tool_modes: dict[str, str], selected_skills: list[str]
    ) -> dict[str, str]:
        """Build a per-tool mode mapping for tools belonging to selected skills.

        Args:
            tool_modes: Mapping of tool name to mode (``"allow"``, ``"ask"``, ``"block"``).
            selected_skills: Skill paths that are currently selected.

        Returns:
            Dict mapping tool name to its configured mode.
        """
        selected = {self.normalize_skill_path(path) for path in selected_skills}
        config = {}
        for tool_info in self.all_tools:
            if tool_info.skill_path in selected:
                mode = tool_modes.get(tool_info.name, "ask")
                config[tool_info.name] = mode
        return config

    def build_tool_config_by_name(
        self, tool_modes: dict[str, str], names: list[str]
    ) -> dict[str, str]:
        """Build a per-tool mode mapping for explicit tool names.

        Unselected tools default to ``"allow"`` because headless sub-agents
        cannot ask for user approval.

        Args:
            tool_modes: Mapping of tool name to mode override.
            names: Selected tool names.

        Returns:
            Dict mapping each discovered tool name to its configured mode.
        """
        known = {tool_info.name for tool_info in self.all_tools}
        return {name: tool_modes.get(name, "allow") for name in names if name in known}

    def default_tool_modes(self) -> dict[str, str]:
        """Return the default ``"ask"`` mode for every discovered tool."""
        return {t.name: "ask" for t in self.all_tools}

    # ------------------------------------------------------------------
    #  Public: UI & lookup
    # ------------------------------------------------------------------

    def get_skill_tree(self) -> dict:
        """Return a nested folder/skill tree for UI rendering.

        Each node is a dict with:
            ``folders`` — dict of child folder name → node
            ``skills`` — list of ``SkillInfo`` objects at this level

        Returns:
            Nested tree dict rooted at the skills directory.
        """
        tree: dict = {"folders": {}, "skills": []}

        for skill in self.skills:
            parts = skill.path.replace("\\", "/").split("/")
            node = tree
            for part in parts[:-1]:
                if part not in node["folders"]:
                    node["folders"][part] = {"folders": {}, "skills": []}
                node = node["folders"][part]
            node["skills"].append(skill)

        return tree

    def get_skill_by_path(self, path: str) -> SkillInfo | None:
        """Look up a ``SkillInfo`` by its relative path."""
        return self._skill_by_path.get(self.normalize_skill_path(path))

    @staticmethod
    def normalize_skill_path(path: str) -> str:
        """Coerce a skill path to its canonical forward-slash form.

        Windows separators are converted so user-typed, stored, and preset
        paths match the forward-slash representation used by the skill tree
        and tool metadata on every platform.

        Args:
            path: A skill relative path using either separator style.

        Returns:
            The canonical forward-slash path.
        """
        return path.replace("\\", "/")

    def path_to_display_name(self, path: str) -> str:
        """Get the display name for a skill path."""
        info = self._skill_by_path.get(self.normalize_skill_path(path))
        return info.name if info else path

    def get_validation_issues(self) -> list[ValidationIssue]:
        """Return all collected validation issues from discovery and cross-checks."""
        return list(self._validation_issues)

    # ------------------------------------------------------------------
    #  Public: Refresh & watching
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Clear all caches and re-discover skills and tools from disk.

        Rebuilds ``skills``, ``skill_paths``, ``_skill_by_path``,
        ``all_tools``, ``tool_names`` and re-runs validation.
        """
        self._tool_cache.clear()
        self._schema_cache.clear()
        self._content_cache.clear()
        self._validation_issues.clear()

        self.skills = self.discover_skills()
        self.skill_paths = [s.path for s in self.skills]
        self._skill_by_path = {s.path: s for s in self.skills}
        self.all_tools = self.scan_all_tools()
        self.tool_names = [t.name for t in self.all_tools]

        self._validate_cross_checks()
        self._print_validation()

    def start_watching(self, callback: Callable[[], None]) -> None:
        """Register a skills-change callback and start the directory watcher.

        Multiple callbacks are supported (one per chat window); registering a
        callback that is already present is a no-op. The watcher itself starts
        lazily on the first registration.

        Uses ``watchdog`` on a background thread.  Events are debounced:
        after the last file event within ``_watcher_debounce_sec``, every
        registered *callback* is invoked (on the watchdog thread — the caller is
        responsible for marshaling to the UI thread).

        Args:
            callback: A callable with no arguments to invoke when skills
                change.
        """
        if callback not in self._watcher_callbacks:
            self._watcher_callbacks.append(callback)
        if self._watcher_observer is not None:
            return

        class _SkillDirEventHandler(FileSystemEventHandler):
            """Debounced event handler — resets timer on each event."""

            def __init__(self, mgr: SkillManager) -> None:
                super().__init__()
                self._mgr = mgr

            def on_any_event(self, event) -> None:
                src = event.src_path if hasattr(event, "src_path") else ""
                parts = Path(src).parts
                if "_presets" in parts:
                    return
                if "references" in parts and "logs" in parts:
                    return
                self._mgr._schedule_refresh()

        event_handler = _SkillDirEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.skills_dir), recursive=True)

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
        """Stop the skills directory watcher and clean up threads / timers."""
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
        self._watcher_callbacks = []

    # ------------------------------------------------------------------
    #  Private: Watcher helpers
    # ------------------------------------------------------------------

    def _schedule_refresh(self) -> None:
        """Schedule a debounced refresh when a file change is detected.

        Thread-safe: uses a lock to cancel and restart the debounce
        timer.  After ``_watcher_debounce_sec`` of inactivity, fires
        the callback.
        """
        with self._watcher_lock:
            if self._watcher_timer is not None:
                self._watcher_timer.cancel()
            self._watcher_timer = threading.Timer(
                self._watcher_debounce_sec,
                self._on_watcher_debounced,
            )
            self._watcher_timer.start()

    def _on_watcher_debounced(self) -> None:
        """Invoke every registered callback after a debounce period."""
        with self._watcher_lock:
            callbacks = list(self._watcher_callbacks)
        for callback in callbacks:
            callback()

    # ------------------------------------------------------------------
    #  Private: Validation
    # ------------------------------------------------------------------

    def _add_issue(self, level: ValidationLevel, source: str, message: str, field: str) -> None:
        self._validation_issues.append(
            ValidationIssue(
                level=level,
                source=source,
                message=message,
                field=field,
            )
        )

    def _validate_cross_checks(self) -> None:
        """Run validation checks that require the full skills/tools list."""
        seen: dict[str, str] = {}
        for skill in self.skills:
            if skill.name in seen:
                self._add_issue(
                    ValidationLevel.ERROR,
                    f"skill:{skill.path}",
                    f"Duplicate skill display name — also defined in '{seen[skill.name]}'.",
                    "name",
                )
            else:
                seen[skill.name] = f"skill:{skill.path}"

    def _print_validation(self) -> None:
        """Log a validation summary with colored tags."""
        errors = [i for i in self._validation_issues if i.level == ValidationLevel.ERROR]
        warnings = [i for i in self._validation_issues if i.level == ValidationLevel.WARNING]

        if not self._validation_issues:
            return

        logger.info("=== Skill Validation Report ===")
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

    def _resolve_skill_path(self, skill_path: str) -> Path | None:
        """Resolve a skill relative path to its directory path.

        Args:
            skill_path: Skill relative path from skills_dir.

        Returns:
            Absolute path to the skill directory, or ``None``.
        """
        if not self.skills_dir.is_dir():
            return None

        entry = self.skills_dir / self.normalize_skill_path(skill_path)
        skill_md = entry / "SKILL.md"
        if entry.is_dir() and skill_md.is_file():
            return entry

        return None
