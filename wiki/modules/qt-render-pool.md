# qt.render_pool — process pool for chat render plans

Source: `src/qt/render_pool.py`

## Purpose

Chat rendering (MarkdownIt, Pygments, matplotlib/LaTeX, token counting) is pure
Python. Running it on a `QThread` still shares the process GIL, so a long render
can starve the GUI thread's Python slots and freeze the app. This module moves
full render plans into separate processes, each with its own interpreter and GIL.
It is used by transcript pre-warming; normal streaming and in-thread rebuilds are
unchanged.

Only plain data crosses the boundary: the message list, the system prompt (the
only snapshot field the context banner reads), the delta banners, and the busy
flag. The returned `RenderPlan` is picklable.

## Deliverables

- `render_plan(messages, system_prompt, banners, is_busy) -> RenderPlan` — async
  wrapper that runs `ChatRenderer.build_plan` in a worker process.
- `shutdown_render_pool()` — stop the pool on application shutdown.
- A lazily created shared `ProcessPoolExecutor` (`_MAX_WORKERS = 2`, clamped to
  the CPU count).

## Steps / Flow

1. `render_plan` gets the running loop and calls `loop.run_in_executor` with the
   shared process pool.
2. The pool pickles the arguments and runs `_render_plan` in a child process:
   it builds a minimal `{"system_prompt": ...}` snapshot and returns
   `ChatRenderer().build_plan(...)`.
3. The child's result is unpickled by the executor and returned to the awaiting
   worker loop.
4. The worker calls `ChatRenderer.adopt_plan(plan)` to seed its local item cache
   and streaming indices, then emits `plan_ready`.

## Notes

- On Windows, `spawn` re-imports the main module (`src.app`), which imports
  PySide6. Each child therefore carries PySide6 memory; the pool is kept small.
- The GUI thread still applies the plan and QML still lays out rich text on the
  GUI thread. The pool only removes the Python render/GIL contention; the
  controller throttles pre-warm inserts separately.

## Function Reference

| Signature | Inputs | Output | Flow | Side effects |
|---|---|---|---|---|
| `def _render_plan(messages, system_prompt, banners, is_busy) -> RenderPlan` | render inputs | `RenderPlan` | build minimal snapshot → `ChatRenderer().build_plan` | runs in a child process |
| `async def render_plan(messages, system_prompt, banners, is_busy) -> RenderPlan` | render inputs | `RenderPlan` | `run_in_executor` on the shared pool | starts the pool on first use |
| `def shutdown_render_pool() -> None` | — | `None` | `shutdown(wait=False, cancel_futures=True)` | stops child processes |
| `def _get_executor() -> ProcessPoolExecutor` | — | executor | lazy create behind a lock | logs pool start |
