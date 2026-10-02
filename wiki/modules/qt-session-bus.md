# qt.session_bus — SessionBus

Source: `src/qt/session_bus.py`

## Purpose

The single shared broadcast hub for **session-list changes**. Every open window
owns a private [`SessionController`](qt-session-controller.md) and therefore a
private session-menu model; the bus lets a create or delete performed anywhere
(the [control server](control-server.md) or an in-app title bar) refresh every
window's title-bar session list at once. `ProcooQtUI` owns the one instance and
hands it to each `SessionController` and to the
[`WindowManager`](qt-window-manager.md).

## Deliverables

- `SessionBus(QObject)` owned by [`qt-ui`](qt-ui.md) as `session_bus`.
- `sessions_changed` signal — subscribed to by every `SessionController`'s
  `refresh_sessions` slot.
- `notify_changed()` — convenience emitter for callers.

## Steps / Flow

### Broadcast

1. A session is created or deleted by the control server
   ([`WindowManager`](qt-window-manager.md)) or by an in-app title bar
   ([`SessionController`](qt-session-controller.md)).
2. The mutator emits `sessions_changed` on the shared bus.
3. Every subscribed `SessionController.refresh_sessions` slot schedules an
   off-thread `refresh_model_async`, resetting that window's
   `SessionMenuModel` so its `SessionSelector.qml` list repaints.

The bus is distinct from each controller's own `sessions_changed` property-notify
signal, so refreshing never re-triggers a broadcast (no re-entrancy).

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def notify_changed(self) -> None` | — | `None` | `sessions_changed.emit()` | Notifies every subscriber |
