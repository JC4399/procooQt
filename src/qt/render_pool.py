"""Process pool for CPU-heavy chat render plans.

The chat render pipeline (MarkdownIt, Pygments, matplotlib/LaTeX, token
counting) is pure Python. Running it on a ``QThread`` still shares the process
GIL, so a long render can starve the GUI thread's Python slots. This module
moves full render plans into separate processes, each with its own interpreter
and GIL, so pre-warming a window's transcripts does not block the main app.

Only plain data crosses the process boundary: the message list, the system
prompt (the only snapshot field the context banner uses), the delta banners, and
the busy flag. The returned :class:`~src.qt.chat_render.RenderPlan` is picklable
(keys, role-keyed item dicts, and streaming indices).
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging
import os
from threading import Lock

from .chat_render import ChatRenderer, RenderPlan

logger = logging.getLogger("procoo_qt")

#: Number of render worker processes. Kept small because each Windows spawn
#: re-imports the app module (and therefore PySide6).
_MAX_WORKERS = 2

_executor: ProcessPoolExecutor | None = None
_executor_lock = Lock()


# ------------------------------------------------------------------
#  Process-side entry point
# ------------------------------------------------------------------


def _render_plan(
    messages: list[dict],
    system_prompt: str,
    banners: list[dict],
    is_busy: bool,
) -> RenderPlan:
    """Build one render plan inside a worker process.

    Args:
        messages: The chat's message list.
        system_prompt: The system prompt for the context banner.
        banners: Delta context banners.
        is_busy: Whether the chat is generating.

    Returns:
        The populated :class:`RenderPlan`.
    """
    snapshot = {"system_prompt": system_prompt}
    return ChatRenderer().build_plan(messages, snapshot, banners, is_busy)


# ------------------------------------------------------------------
#  Main-process API
# ------------------------------------------------------------------


def _get_executor() -> ProcessPoolExecutor:
    """Return the shared process pool, creating it on first use.

    Returns:
        The process pool executor.
    """
    global _executor
    if _executor is not None:
        return _executor
    with _executor_lock:
        if _executor is None:
            workers = max(1, min(_MAX_WORKERS, os.cpu_count() or 1))
            _executor = ProcessPoolExecutor(max_workers=workers)
            logger.info("Chat render pool started (%d processes)", workers)
        return _executor


async def render_plan(
    messages: list[dict],
    system_prompt: str,
    banners: list[dict],
    is_busy: bool,
) -> RenderPlan:
    """Render a plan in a worker process without blocking the caller's loop.

    Args:
        messages: The chat's message list.
        system_prompt: The system prompt for the context banner.
        banners: Delta context banners.
        is_busy: Whether the chat is generating.

    Returns:
        The populated :class:`RenderPlan`.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _get_executor(),
        _render_plan,
        messages,
        system_prompt,
        banners,
        is_busy,
    )


def shutdown_render_pool() -> None:
    """Stop the render process pool (application shutdown)."""
    global _executor
    with _executor_lock:
        executor = _executor
        _executor = None
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)
        logger.info("Chat render pool stopped")
