# app — entry point

Source: `procooQt/src/app.py`

## Purpose

Top-level application bootstrap. Wires together the config, skill, session,
and preset subsystems, configures colored logging, and launches the Qt Quick /
QML UI on a fused `qasync` + Qt event loop.

## Deliverables

- `ProcooApp` instance holding `config`, `skill_manager`, `session_store`, and
  `preset_store`.
- `_register_fonts()` — registers the bundled `Sarasa Fixed TC` font.
- `main()` — Qt entry point that builds the `QApplication`, `qasync` event
  loop, and `QQmlApplicationEngine`, then loads `qml/Main.qml`.

## Steps / Flow

1. `setup_colored_logging(INFO)` and quiet `httpx`.
2. Build `ProcooApp(<project_root>/config)`; on `ProcooError`, log critical and
   `sys.exit(1)`.
3. `QQuickStyle.setStyle("Basic")` → `QApplication(sys.argv)` → `_register_fonts()`.
4. Create `qasync.QEventLoop(qt_app)` and `asyncio.set_event_loop(loop)`.
5. Build `QQmlApplicationEngine()` → `ProcooQtUI(backend, engine)`; load
   `qml/Main.qml`; exit if the engine produced no root objects.
6. `ui.start()`; then `loop.run_forever()`.

## Function Reference

### `ProcooApp`

| | |
|---|---|
| Attributes | `config`, `skill_manager`, `session_store`, `preset_store`. |

### `ProcooApp.__init__`

| | |
|---|---|
| Signature | `def __init__(self, config_dir: str = "./config") -> None` |
| Inputs | `config_dir` — config directory. |
| Output | `None` |
| Flow | `ConfigManager(config_dir)` → resolve `config.skills_dir` → `SkillManager(skills)` → `SessionStore(resolve(config.storage_dir))` → `PresetStore(skills/_presets)`. |

### `ProcooApp._resolve`

| | |
|---|---|
| Signature | `@staticmethod def _resolve(path_str: str) -> str` |
| Inputs | `path_str` (`str`) — a path from `config.yaml`. |
| Output | absolute, resolved path string. |
| Flow | non-absolute paths are resolved against `<project_root>` (`procooQt/`). |

### `_register_fonts`

| | |
|---|---|
| Signature | `def _register_fonts() -> None` |
| Output | `None` |
| Flow | `QFontDatabase.addApplicationFont(assets/fonts/SarasaFixedTC-Regular.ttf)`; logs info, or warning if missing. |

### `main`

| | |
|---|---|
| Signature | `def main() -> None` |
| Output | `None` |
| Flow | logging + backend → `QApplication` → qasync loop → QML engine + `ProcooQtUI` → load `Main.qml` → `ui.start()` → `loop.run_forever()`. |
