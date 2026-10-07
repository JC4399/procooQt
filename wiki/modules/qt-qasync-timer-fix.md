# qt.qasync_timer_fix — qasync Qt-timer leak workaround

Source: `src/qt/qasync_timer_fix.py`

## Purpose

qasync 0.28.0 (the latest release) schedules every asyncio timer through its
private `_SimpleTimer`, which starts one `QObject` timer per callback and only
calls `killTimer` when that timer actually **fires**. A callback cancelled before
its deadline therefore leaves its Win32 USER timer alive for the full remaining
deadline.

The OpenAI/httpx streaming path triggers this heavily: httpcore wraps every HTTP
read in `anyio.fail_after(read_timeout)` and the OpenAI client's default timeout
is 600 seconds. Each streamed chunk schedules a 600 s deadline and cancels it as
soon as the chunk arrives, so each chunk leaks a USER timer for ~10 minutes.
Enough chunks exhaust the per-process USER-handle allowance; after that
`QEventDispatcherWin32::registerTimer` fails and every QML `Timer` / animation
(streaming spinners, cursor blink, tab blink) silently stops — the chat appears
frozen even though tokens keep arriving.

This module monkeypatches `_SimpleTimer` **in memory** so cancelling a callback
also kills its Qt timer immediately. It never edits the installed package. The
fix is platform-independent (the leak also exists on Unix, just without the hard
USER-handle ceiling).

## Deliverables

- `_CancelAwareHandle` — a forwarding proxy around an `asyncio.Handle` that
  releases the owning Qt timer when `cancel()` is called.
- `install_qasync_timer_patch()` — idempotent installer that replaces
  `_SimpleTimer.add_callback` and adds `_SimpleTimer._release`.
- `_INSTALLED` — module-level guard flag.

## Steps / Flow

1. `app.main` calls `install_qasync_timer_patch()` before creating the
   `qasync.QEventLoop`, so the loop's `_SimpleTimer` instance uses the patched
   class methods.
2. `install_qasync_timer_patch()`:
   - Returns immediately if `_INSTALLED` is already true.
   - Resolves `qasync._SimpleTimer` and installs two functions on the class:
     - `add_callback(self, handle, delay)` — starts the Qt timer, wraps the
       handle in `_CancelAwareHandle`, stores the **proxy** in the
       name-mangled `__callbacks` map, and returns the proxy. (Storing the proxy
       is required so `timerEvent`'s `handle._run()` / `handle._cancelled`
       accesses forward to the real handle.)
     - `_release(self, timer_id, proxy)` — deletes the callback entry and calls
       `killTimer` only if the id still maps to the same proxy.
   - Sets `_INSTALLED = True` and logs.
3. When anyio (or `asyncio.wait_for` / `asyncio.timeout`) cancels a deadline
   handle, `_CancelAwareHandle.cancel()` cancels the real handle and immediately
   calls `_release`, freeing the Win32 timer instead of waiting for its deadline.
4. A normally-fired timer is still cleaned up by qasync's own `timerEvent`, which
   deletes the entry and calls `killTimer`; a later `cancel()` then finds no
   matching entry and is a no-op (no double `killTimer`).

## Function Reference

### `_CancelAwareHandle`

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def __init__(self, handle: asyncio.Handle, timer: Any, timer_id: int) -> None` | `handle` — real asyncio handle; `timer` — owning `_SimpleTimer`; `timer_id` — Qt timer id | `None` | Stores the three fields in `__slots__` | — |
| `def __getattr__(self, name: str) -> Any` | `name` — attribute name | wrapped handle's attribute | Forwards all non-slot attribute access (`_run`, `_cancelled`, `_callback`, `_loop`, …) to the real handle | `AttributeError` if absent on the handle |
| `def cancel(self) -> None` | — | `None` | `handle.cancel()`; if a timer is still owned, `timer._release(timer_id, self)` then clear the reference | Calls `_SimpleTimer._release` → `killTimer` |

### Module functions

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def install_qasync_timer_patch() -> None` | — | `None` | Guard on `_INSTALLED`; import `qasync`; assign `_SimpleTimer.add_callback` / `_release`; log | Mutates the qasync `_SimpleTimer` class for the process lifetime |

### Constants

| Name | Value / Type | Meaning |
|---|---|---|
| `_INSTALLED` | `bool` | Idempotence guard; `True` once the class has been patched |

## See also

- [app](app.md) — installs the patch before the event loop is created.
- [chat-llm](chat-llm.md) — OpenAI async client whose 600 s default timeout
  drives the per-chunk timer churn.
- [chat-controller](qt-chat-controller.md) — streaming loop that renders tokens.
