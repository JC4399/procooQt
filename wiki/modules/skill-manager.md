# skill.manager — SkillManager

Source: `procooQt/src/skill/manager.py`

## Purpose

Discovers, loads, and manages skills and their tools. Scans a `skills/`
directory for `SKILL.md` files, validates them, infers tool schemas from
Python scripts via AST, and watches the directory for live changes.

## Deliverables

- `skills` (`list[SkillInfo]`), `skill_paths`, `all_tools` (`list[ToolInfo]`),
  `tool_names`.
- `load_skill_content(s)` / `load_skill_contents(paths)` (full content).
- `scan_tools` / `scan_all_tools` (cached tool discovery).
- `load_tool_functions(selected_skills)` — OpenAI-compatible tool defs with
  inferred JSON Schema.
- `get_skill_tree` (nested UI tree), `build_tool_config`, `default_tool_modes`.
- `refresh`, `start_watching`, `stop_watching` (watchdog-based live reload).
- `get_validation_issues` (errors/warnings).

## Skill directory format

```
skills/
  <group>/
    <skill>/          # contains SKILL.md -> a skill
      SKILL.md        # YAML frontmatter: name, description; body = instructions
      scripts/        # optional; *.py files become tools (each has run() fn)
```

Skill identity = relative path from `skills_dir` (e.g. `"coding/python"`).
A directory with no `SKILL.md` is treated as a grouping folder.

## Steps / Flow

### Discovery (`discover_skills`)

1. `rglob("SKILL.md")` sorted.
2. For each, `frontmatter.load`; parse `name`/`description`/`instructions`.
3. Validate: `name`, `description`, `instructions` required (else `ERROR`
   issue + skip); `scripts/` with no `.py` → `WARNING`.
4. Append `SkillInfo`.

### Schema inference (`_infer_tool_schema`)

1. Read + `ast.parse` the `.py` (cache result).
2. Find top-level `run` / `async def run`.
3. `ast.get_docstring` → first paragraph = description; `Args:` → param docs.
4. For each arg: map type annotation → JSON Schema type; no-default ⇒ `required`.
5. Cache and return `{description, parameters}`.

### Cross-checks (`_validate_cross_checks`)

- Flags duplicate skill display names across the whole tree.

## Function Reference

### Public

| Function | Signature | Purpose |
|---|---|---|
| `discover_skills` | `() -> list[SkillInfo]` | scan for `SKILL.md` |
| `load_skill_content` | `(skill_path: str) -> SkillContent \| None` | full content of one skill |
| `load_skill_contents` | `(skill_paths: list[str]) -> list[dict]` | dump many skills |
| `scan_tools` | `(skill_path: str) -> list[ToolInfo]` | cached tool scan |
| `scan_all_tools` | `() -> list[ToolInfo]` | all tools across skills |
| `load_tool_functions` | `(selected_skills: list[str]) -> list[dict]` | tool defs with inferred schema |
| `build_tool_config` | `(tool_modes: dict, selected_skills: list[str]) -> dict[str, str]` | per-tool mode map |
| `default_tool_modes` | `() -> dict[str, str]` | `"ask"` for every tool |
| `get_skill_tree` | `() -> dict` | nested `{folders, skills}` tree |
| `get_skill_by_path` | `(path: str) -> SkillInfo \| None` | lookup by path |
| `path_to_display_name` | `(path: str) -> str` | display name for path |
| `get_validation_issues` | `() -> list[ValidationIssue]` | collected issues |
| `refresh` | `() -> None` | clear caches, re-discover |
| `start_watching` | `(callback: Callable[[], None]) -> None` | watch dir for changes |
| `stop_watching` | `() -> None` | stop watcher |

### Private (key)

| Function | Signature | Purpose |
|---|---|---|
| `_infer_tool_schema` | `(script_path: str, tool_name: str) -> dict` | AST-based schema |
| `_find_run_function` | `(tree) -> FunctionDef \| AsyncFunctionDef \| None` | locate `run()` |
| `_ast_type_to_json_schema` | `(node, param_name) -> dict` | annotation → JSON Schema |
| `_resolve_ast_type` | `(node, param_name) -> str \| None` | resolve type string |
| `_parse_google_docstring` | `(docstring) -> dict[str, str]` | description + param docs |
| `_arg_has_default` | `(arg, func) -> bool` | default-value check |
| `_resolve_skill_path` | `(skill_path) -> Path \| None` | resolve to dir |
| `_validate_cross_checks` | `() -> None` | duplicate-name check |
| `_print_validation` | `() -> None` | log report |

### `SkillManager.__init__`

| | |
|---|---|
| Signature | `def __init__(self, skills_dir: str) -> None` |
| Inputs | `skills_dir` — root skills path. |
| Output | `None` |
| Flow | init caches/threading fields → `discover_skills` → `scan_all_tools` → `_validate_cross_checks` → `_print_validation`. |
