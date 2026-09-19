"""Tool: execute Python code or shell commands. Dispatches on the `mode` parameter."""

import asyncio
import json
import os
import re
import sys
import tempfile
import traceback

MAX_LINES = 500
MAX_CHARS = 15000

DENY_PATTERNS = [
    (r"\brm\s+-[rf]{1,2}\b", "rm -r / rm -rf (recursive delete)"),
    (r"\brmdir\s+/[sq]\b", "rmdir with force/quiet flags"),
    (r">\s*/dev/sd[a-z]", "redirect to raw disk device"),
    (r"\bdd\s+if=", "dd (disk writing)"),
    (r"\b(shutdown|reboot|poweroff|halt)\b", "system power control"),
    (r"\b(mkfs|diskpart|format)\b", "disk formatting"),
    (r":\(\)\s*\{[^}]*\};\s*:", "fork bomb"),
    (r"\bkill\s+-9\s+\$\$", "self-destruct kill -9 $$"),
    (r"\bxargs\s+rm\b", "xargs rm (bulk delete pipeline)"),
]


def _guard(command: str) -> str | None:
    for pattern, label in DENY_PATTERNS:
        if re.search(pattern, command):
            return f"Blocked by safety guard ({label}): {command}"
    return None


# ------------------------------------------------------------------
#  Virtual environment detection
# ------------------------------------------------------------------


def _detect_venv() -> str | None:
    """Return the venv scripts directory if running inside a virtual environment.

    Returns:
        Path to ``Scripts/`` (Windows) or ``bin/`` (Unix) inside the venv,
        or ``None`` if not running in a virtual environment.
    """
    if sys.prefix == sys.base_prefix:
        return None
    if os.name == "nt":
        return os.path.join(sys.prefix, "Scripts")
    return os.path.join(sys.prefix, "bin")


def _venv_env() -> dict[str, str] | None:
    """Build an environment dict with the venv active.

    Prepends the venv's scripts directory to ``PATH`` and sets
    ``VIRTUAL_ENV`` so that any shell command spawned from this
    process inherits the same virtual environment.

    Returns:
        A copy of ``os.environ`` with venv paths injected, or ``None``
        if not running in a virtual environment.
    """
    venv_scripts = _detect_venv()
    if venv_scripts is None:
        return None
    env = os.environ.copy()
    env["PATH"] = venv_scripts + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = sys.prefix
    return env


def _truncate_output(raw: str) -> str:
    """Cap output at MAX_LINES lines or MAX_CHARS characters.

    When either limit is hit, a header is prepended stating which limit was
    hit and the total size of the full output.

    Args:
        raw: The full combined output string to cap.

    Returns:
        The (possibly truncated) output string.
    """
    if not raw:
        return raw

    lines = raw.splitlines()
    total_lines = len(lines)
    total_chars = len(raw)

    output_lines: list[str] = []
    char_count = 0
    hit_line_limit = False
    hit_char_limit = False

    for i, line in enumerate(lines):
        output_lines.append(line)
        char_count += len(line) + 1  # +1 for the newline we'll join with
        if i + 1 >= MAX_LINES:
            hit_line_limit = True
            break
        if char_count >= MAX_CHARS:
            hit_char_limit = True
            break

    result = ""

    if hit_line_limit:
        result += (
            f"(Output limited to first {MAX_LINES} lines. "
            f"Full output has {total_lines} lines total.)\n"
        )
    elif hit_char_limit:
        result += (
            f"(Output limited to first {MAX_CHARS} characters. "
            f"Full output has {total_chars} characters total.)\n"
        )

    result += "\n".join(output_lines)
    return result if result else "(no output)"


async def _shell(command: str, timeout: int) -> str:
    blocked = _guard(command)
    if blocked:
        return blocked

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_venv_env(),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            error_text = stderr.decode("utf-8", errors="replace")
            output += f"\n[stderr]\n{error_text}"

        return _truncate_output(output.strip())
    except TimeoutError:
        return f"Shell command timed out after {timeout}s."
    except Exception as e:
        return f"Shell execution error: {e}"


async def _python(code: str, timeout: int) -> str:
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            tmp_path = f.name

        orig_cwd = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_venv_env(),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        finally:
            os.chdir(orig_cwd)
            os.unlink(tmp_path)

        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            error_text = stderr.decode("utf-8", errors="replace")
            output += f"\n[stderr]\n{error_text}"

        return _truncate_output(output.strip())
    except TimeoutError:
        return f"Python execution timed out after {timeout}s."
    except Exception as e:
        return f"Python execution error: {e}"


async def run(
    mode: str,
    code: str = "",
    command: str = "",
    timeout: int = 30,
) -> str:
    """Execute Python code or a shell command.

    Args:
        mode: Execution mode — "python" or "shell".
        code: (python) Python source code to execute.
        command: (shell) Shell command string to run.
        timeout: Maximum execution time in seconds. Defaults to 30.
    """
    try:
        if mode == "python":
            return await _python(code, timeout)
        elif mode == "shell":
            return await _shell(command, timeout)
        else:
            return f"Unknown mode: {mode}. Valid modes: python, shell."
    except Exception:
        return json.dumps({"error": traceback.format_exc()})


if __name__ == "__main__":
    args = json.loads(sys.stdin.read())
    result = asyncio.run(run(**{k: v for k, v in args.items() if v is not None}))
    print(result)
