"""Virtual-environment resolution for tool subprocesses.

Resolves the Python interpreter and environment that tool scripts run
under, so python/shell execution always targets the project ``.venv``
rather than relying on whichever interpreter happened to launch the app.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys

logger = logging.getLogger("procoo_qt")


def _project_root() -> Path:
    """Return the project root directory (parent of ``src``)."""
    return Path(__file__).resolve().parent.parent.parent


def _venv_python_path() -> Path:
    """Return the project ``.venv`` interpreter path.

    The project is installed via ``start_procoo.bat``, which creates a
    ``.venv`` at the project root, so the path is hardcoded relative to
    this module.

    Returns:
        Absolute path to ``.venv/Scripts/python.exe`` (Windows) or
        ``.venv/bin/python`` (Unix).
    """
    scripts = "Scripts" if os.name == "nt" else "bin"
    python = "python.exe" if os.name == "nt" else "python"
    return _project_root() / ".venv" / scripts / python


def _is_venv_interpreter(python_path: Path) -> bool:
    """Return whether *python_path* sits inside a virtual environment.

    A venv is identified by a ``pyvenv.cfg`` in the directory above the
    interpreter's ``Scripts``/``bin`` directory.

    Args:
        python_path: Absolute path to a Python interpreter.

    Returns:
        ``True`` when the interpreter belongs to a virtual environment.
    """
    prefix = python_path.parent.parent
    return (prefix / "pyvenv.cfg").is_file()


# ------------------------------------------------------------------
#  Public API
# ------------------------------------------------------------------


def resolve_tool_python() -> str:
    """Return the absolute path to the Python interpreter tools should run under.

    Prefers the current interpreter when the app is already running inside
    a virtual environment.  Otherwise resolves the project ``.venv`` and
    falls back to ``sys.executable`` when no venv can be located.

    Returns:
        Absolute path string to the target Python interpreter.
    """
    if sys.prefix != sys.base_prefix:
        return sys.executable

    venv_python = _venv_python_path()
    if venv_python.is_file():
        logger.info("Tool Python resolved to project venv: %s", venv_python)
        return str(venv_python)

    logger.warning("No project venv found; tool Python falls back to %s", sys.executable)
    return sys.executable


def build_tool_env(python_path: str | None = None) -> dict[str, str]:
    """Build an environment dict with the target venv activated.

    Prepends the venv scripts directory to ``PATH`` and sets
    ``VIRTUAL_ENV`` so shell commands spawned by tools resolve
    ``python``/``pip`` to the same venv as the resolved interpreter.

    Args:
        python_path: Optional interpreter path; defaults to the resolved
            tool Python.

    Returns:
        A copy of ``os.environ`` with the venv injected.  When the target
        interpreter is not inside a virtual environment, returns an
        unmodified copy.
    """
    target = Path(python_path) if python_path else Path(resolve_tool_python())

    env = os.environ.copy()
    if _is_venv_interpreter(target):
        scripts_dir = target.parent
        env["PATH"] = str(scripts_dir) + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(scripts_dir.parent)
    return env
