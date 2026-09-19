# skill.models — Pydantic data models

Source: `procooQt/src/skill/models.py`

## Purpose

Pydantic models describing skills, tools, and validation issues used across
skill discovery and loading.

## Deliverables

- `ValidationLevel` (StrEnum: `error` | `warning`).
- `ValidationIssue`, `SkillInfo`, `SkillContent`, `ToolInfo` models.

## Model Reference

### `ValidationLevel`

| Value | Meaning |
|---|---|
| `error` | blocking issue (skill skipped). |
| `warning` | non-blocking issue. |

### `ValidationIssue`

| Field | Type | Description |
|---|---|---|
| `level` | `ValidationLevel` | severity |
| `source` | `str` | e.g. `"skill:Weather Lookup"` |
| `message` | `str` | human-readable description |
| `field` | `str = ""` | problematic field name |

### `SkillInfo`

Summary metadata for a discovered skill.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | display name (frontmatter or dir name) |
| `path` | `str` | relative path from skills_dir (e.g. `"coding/python"`) |
| `description` | `str` | short description |
| `has_tools` | `bool = False` | has `scripts/` subdirectory |

### `SkillContent`

Full loaded skill content.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | display name |
| `path` | `str` | relative path |
| `description` | `str` | short description |
| `instructions` | `str` | SKILL.md markdown body (system-prompt content) |
| `scripts` | `list[str]` | filenames in `scripts/` |

### `ToolInfo`

Metadata for a single tool script.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | filename without `.py` |
| `skill_path` | `str` | parent skill relative path |
| `description` | `str` | first line of `run()` docstring |
| `filepath` | `str` | absolute path to the `.py` file |
