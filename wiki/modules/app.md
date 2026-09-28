# app — entry point

Source: `procooQt/src/app.py`

## Purpose

Top-level application bootstrap. Wires together the config, skill, chat,
and preset subsystems, configures colored logging, and launches the Qt Quick /
QML UI on a fused `qasync` + Qt event loop.

## Deliverables

- `ProcooApp` instance holding `config`, `skill_manager`, `chat_store`,
  `preset_store`, `capabilities_dir`, `automation_manager`, and
  `notification_manager`.
- `_register_fonts()` — registers the bundled `Sarasa Fixed TC` font.
- `_set_app_user_model_id()` — sets a stable Windows AppUserModelID so the
  taskbar groups the app under its own icon instead of `python.exe`.
- `_set_app_icon()` — applies `assets/logos/logo.png` as the application-wide
  window, title-bar, and taskbar icon.
- `main()` — Qt entry point that builds the `QApplication`, `qasync` event
  loop, and `QQmlApplicationEngine`, then loads `src/qml/Main.qml`.
- Native frame installation for the frameless main window via
  [`qt-native-frame`](qt-native-frame.md) (`native_frame.install`), restoring
  edge resize and Aero Snap while keeping the custom QML title bar.

## Steps / Flow

1. `setup_colored_logging(INFO)` and quiet `httpx`; `_set_app_user_model_id()`
   (Windows only) before any window exists.
2. Build `ProcooApp(<project_root>/config)`; on `ProcooError`, log critical and
   `sys.exit(1)`.
3. `QQuickStyle.setStyle("Basic")` → `QApplication(sys.argv)` →
   `_set_app_icon(qt_app)` → `_register_fonts()`.
4. Create `qasync.QEventLoop(qt_app)` and `asyncio.set_event_loop(loop)`.
5. Build `QQmlApplicationEngine()` → `ProcooQtUI(backend, engine)`; load
   `src/qml/Main.qml`; exit if the engine produced no root objects.
6. Install the frameless-window native frame filter on the loaded root window
   (`native_frame.install(qt_app, root_window)`), keeping the returned filter
   referenced; see [`qt-native-frame`](qt-native-frame.md).
7. `ui.start()`; then `loop.run_forever()`.

## Function Reference

### `ProcooApp`

| | |
|---|---|
| Attributes | `config`, `skill_manager`, `chat_store`, `preset_store`, `capabilities_dir`, `automation_manager`, `notification_manager`. |

### `ProcooApp.__init__`

| | |
|---|---|
| Signature | `def __init__(self, config_dir: str = "./config") -> None` |
| Inputs | `config_dir` — config directory. |
| Output | `None` |
| Flow | `ConfigManager(config_dir)` → resolve `skills_dir` / `storage_dir` / `capabilities_dir` → `SkillManager(skills)` → `ChatStore(storage)` → `PresetStore(skills/_presets)` → `AutomationManager(resolve(automations_dir), storage)` → `NotificationManager(storage)`. |

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

### `_set_app_user_model_id`

| | |
|---|---|
| Signature | `def _set_app_user_model_id() -> None` |
| Output | `None` |
| Flow | On `sys.platform == "win32"`, calls `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("procoo.qt")`; no-op elsewhere. |

### `_set_app_icon`

| | |
|---|---|
| Signature | `def _set_app_icon(qt_app: QApplication) -> None` |
| Inputs | `qt_app` (`QApplication`) — the running application instance. |
| Output | `None` |
| Flow | Sets `qt_app.setWindowIcon(QIcon(assets/logos/logo.png))`; logs info, or warning if missing. All top-level windows (including the QML `ApplicationWindow`) inherit it. |

### `main`

| | |
|---|---|
| Signature | `def main() -> None` |
| Output | `None` |
| Flow | logging + AppUserModelID → backend → `QApplication` + app icon → qasync loop → QML engine + `ProcooQtUI` → load `Main.qml` → `native_frame.install(qt_app, root_window)` → `ui.start()` → `loop.run_forever()`. |
