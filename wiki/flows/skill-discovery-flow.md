# Skill discovery flow

How the `skills/` directory becomes skills, tools, and OpenAI tool schemas.

Related: [`skill-manager`](../modules/skill-manager.md), [`skill-models`](../modules/skill-models.md), [`qt-skill-controller`](../modules/qt-skill-controller.md).

The library is shared with the Flet edition at `../skills` (resolved against
the procooQt project root); only `_presets/` is written by this app.

## Directory layout

```
skills/
  <group>/
    <skill>/            # SKILL.md => a skill
      SKILL.md          # frontmatter: name, description; body: instructions
      scripts/          # *.py => tools (each exposes run())
  _presets/             # preset JSON files (ignored by the watcher)
```

## Sequence

### 1. Discovery (`discover_skills`)

1. `rglob("SKILL.md")` sorted.
2. `frontmatter.load` each; read `name`, `description`, `instructions`.
3. Validate: missing `name` / `description` / empty body → `ERROR` issue +
   skip; a `scripts/` directory with no `.py` files → `WARNING`.
4. `has_tools = (entry/scripts).is_dir()`.
5. Append `SkillInfo`.

### 2. Tool scan (`scan_tools` / `scan_all_tools`)

1. For each skill's `scripts/`, list `*.py` (skip `_`-prefixed).
2. Tool name = filename without `.py`.
3. `ToolInfo(name, skill_path, description, filepath)`.
4. Cached per skill path.

### 3. Schema inference (`_infer_tool_schema`)

1. `ast.parse` the script (cache result).
2. Find top-level `run` / `async def run`.
3. `ast.get_docstring` → first paragraph = description; `Args:` section → param
   docs.
4. For each arg: annotation → JSON Schema type via `_resolve_ast_type`
   (`str/int/float/bool/list/dict`, `X | None`, `Optional[X]`).
5. No default value ⇒ `required`.
6. Cache `{description, parameters}`.

### 4. Tool defs (`load_tool_functions`)

Combine scan + schema into OpenAI-compatible defs:

```python
{"name", "description", "parameters", "script_path", "skill_path", "type"}
```

### 5. Cross-checks (`_validate_cross_checks`)

Flag duplicate skill display names across the tree.

### 6. Watch (`start_watching`)

`watchdog.Observer` on `skills_dir` (recursive). Events are debounced (0.5s);
paths containing `_presets` are ignored. The debounced callback runs **on the
watchdog thread** and, per the concurrency rules, only emits a Qt signal:
`SkillController.skill_files_changed`. The connected slot
`_handle_skill_files_changed` runs queued on the GUI thread, then
`asyncio.to_thread(skill_manager.refresh)` re-runs the whole pipeline off-loop
and `_rebuild_skill_sidebar` rebuilds the `SkillTreeModel` and `ToolModeModel`
(preserving selections that still exist).

The editor file tree is built from `skills_dir` by `EditorController.start`
and file clicks; it is not rebuilt by the skill watcher.

## Validation levels

| Level | Effect |
|---|---|
| `error` | skill skipped during discovery |
| `warning` | logged, skill still loaded |

At startup `SessionController.start` calls `_emit_validation_issues`, which
surfaces the collected errors and warnings as toasts. `SkillController.build`
also populates the initial skill tree and the defaults for every discovered
tool (mode `ask`).
