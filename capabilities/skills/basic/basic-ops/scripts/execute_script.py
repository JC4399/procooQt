"""Tool: execute Python code, shell commands, or a skill script. Dispatches on `mode`."""

import asyncio
import json
import os
from pathlib import Path
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
        if os.name == "nt":
            proc = await asyncio.create_subprocess_exec(
                "powershell",
                "-NoProfile",
                "-Command",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_venv_env(),
            )
        else:
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


async def _skill(script: str, params: dict | None, timeout: int) -> str:
    """Invoke a skill script by piping a JSON argument object to its stdin.

    Runs the script directly (no shell), so the JSON parameter object never
    passes through PowerShell quoting. The script must follow the skill-script
    contract: read one JSON object from stdin and call ``run(**args)``.

    Args:
        script: Absolute path to the skill's ``.py`` script.
        params: Argument object forwarded to the script's ``run(**params)``.
        timeout: Maximum execution time in seconds.

    Returns:
        The script's stdout output as a string, or an error/timeout message.
    """
    if not script:
        return "skill mode requires 'script' (absolute path to the skill script)."

    path = Path(script)
    if not path.is_file():
        return f"Skill script not found: {script}"

    if params is None:
        params = {}
    elif isinstance(params, str):
        try:
            params = json.loads(params)
        except (json.JSONDecodeError, TypeError):
            return f"Skill script '{path.name}' received invalid params JSON: {params[:200]}"

    args_json = json.dumps(params, ensure_ascii=False)

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_venv_env(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(args_json.encode("utf-8")),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            return f"Skill script '{path.name}' timed out after {timeout}s."

        output = stdout.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        stderr_output = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

        if proc.returncode is not None and proc.returncode != 0:
            detail = stderr_output or output.strip()
            return f"Skill script '{path.name}' exited with code {proc.returncode}. {detail[:1000]}"
        if stderr_output:
            output += f"\n[stderr]\n{stderr_output}"

        return output.strip() or "(no output)"
    except Exception as e:
        return f"Skill script execution error: {e}"


def _first_str(*values: object) -> str:
    """Return the first non-empty string among *values*.

    Args:
        *values: Candidate values; non-strings and empty strings are skipped.

    Returns:
        The first non-empty string, or ``""`` when none is found.
    """
    for value in values:
        if isinstance(value, str) and value:
            return value
    return ""


def _is_script_path(value: str) -> bool:
    """Return whether *value* looks like a path to a Python script, not inline code.

    Args:
        value: The candidate source string.

    Returns:
        ``True`` for a single-line ``.py`` path (with a directory separator or an
        existing file); ``False`` for inline source code.
    """
    stripped = value.strip()
    if "\n" in stripped or not stripped.endswith(".py"):
        return False
    return os.sep in stripped or "/" in stripped or Path(stripped).is_file()


# ------------------------------------------------------------------
#  Public entry point
# ------------------------------------------------------------------


async def run(
    mode: str,
    code: str = "",
    command: str = "",
    script: str = "",
    params: dict | None = None,
    timeout: int = 600,
) -> str:
    """Execute Python code, a shell command, or a skill script.

    Args:
        mode: Execution mode — "python", "shell", or "skill".
        code: (python) Python source code to execute.
        command: (shell) Shell command string to run.
        script: (skill) Absolute path to the skill's ``.py`` script. For
            python mode it is accepted as an alias for ``code``.
        params: (skill only) Argument object forwarded to the skill script's
            ``run(**params)``. Do not nest ``code``/``command``/``script``
            inside it — the top-level arguments are the canonical form.
        timeout: Maximum execution time in seconds. Defaults to 600 (10 minutes).
    """
    try:
        nested = params if isinstance(params, dict) else {}
        src_code = _first_str(code, nested.get("code"))
        src_command = _first_str(command, nested.get("command"))
        src_script = _first_str(script, nested.get("script"))

        if mode == "python":
            source = src_code or src_script
            if not source:
                return "python mode requires 'code' (Python source to execute)."
            if _is_script_path(source):
                return await _skill(source, params, timeout)
            return await _python(source, timeout)
        elif mode == "shell":
            shell_command = src_command or src_script or src_code
            if not shell_command:
                return "shell mode requires 'command' (shell command string to run)."
            return await _shell(shell_command, timeout)
        elif mode == "skill":
            path = src_script or src_code
            return await _skill(path, params, timeout)
        else:
            return f"Unknown mode: {mode}. Valid modes: python, shell, skill."
    except Exception:
        return json.dumps({"error": traceback.format_exc()})


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    args = json.loads(sys.stdin.read())
    result = asyncio.run(run(**{k: v for k, v in args.items() if v is not None}))
    sys.stdout.reconfigure(encoding="utf-8")
    print(result)
