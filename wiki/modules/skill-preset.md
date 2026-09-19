# skill.preset — PresetStore

Source: `procooQt/src/skill/preset.py`

## Purpose

JSON-backed CRUD store for skill/tool configuration presets. Each preset is a
single JSON file in the presets directory (`skills_dir/_presets`).

## Deliverables

- `PresetStore` persisting preset dicts to disk.
- `list_presets`, `load_preset`, `save_preset`, `delete_preset`.

## Steps / Flow

- `save_preset` injects a `"name"` key into the config dict and writes
  `<name>.json`.
- `list_presets` returns sorted `.json` stems.
- `delete_preset` unlinks the file if it exists.

## Function Reference

### `PresetStore`

| | |
|---|---|
| Attributes | `presets_dir` (`Path`). |

### `PresetStore.__init__`

| | |
|---|---|
| Signature | `def __init__(self, presets_dir: str) -> None` |
| Inputs | `presets_dir` — filesystem path to presets directory. |
| Output | `None` |
| Side effects | creates the directory if missing. |

### `list_presets`

| | |
|---|---|
| Signature | `def list_presets(self) -> list[str]` |
| Output | sorted preset names. |

### `load_preset`

| | |
|---|---|
| Signature | `def load_preset(self, name: str) -> dict \| None` |
| Inputs | `name` — preset name (no `.json`). |
| Output | preset dict, or `None` if not found. |

### `save_preset`

| | |
|---|---|
| Signature | `def save_preset(self, name: str, config: dict) -> None` |
| Inputs | `name` — preset name; `config` — settings dict (`name` key injected). |
| Output | `None` |

### `delete_preset`

| | |
|---|---|
| Signature | `def delete_preset(self, name: str) -> None` |
| Inputs | `name` — preset name. |
| Output | `None` |
