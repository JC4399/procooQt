"""Tool: file path search with optional content filter as second layer.

Always searches file paths first via regex pattern against file and
directory paths.  Optionally accepts a ``content`` regex pattern as a
second layer to further filter path-matched files by searching their
contents.  Uses ripgrep for speed when available, with a pure-Python
fallback.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import sys
import traceback

MAX_RESULTS = 100
MAX_LINE_LENGTH = 2000

_SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules"})


# ------------------------------------------------------------------
#  Ripgrep detection
# ------------------------------------------------------------------

def _get_rg_path() -> Path | None:
    """Return the platform-appropriate ripgrep binary path, or None.

    Looks for ``rg`` (Linux/macOS) or ``rg.exe`` (Windows) in the
    ``_executable`` directory relative to this script.
    """
    script_dir = Path(__file__).resolve().parent
    bin_dir = script_dir / "_executable"
    if sys.platform == "win32":
        rg = bin_dir / "rg.exe"
    else:
        rg = bin_dir / "rg"
    return rg if rg.is_file() else None


# ------------------------------------------------------------------
#  Shared helpers
# ------------------------------------------------------------------

def _walk_files(search_dir: Path) -> list[Path]:
    """Recursively collect files, pruning _SKIP_DIRS subtrees.

    Uses os.scandir for fast, lazy iteration without stat-per-entry
    overhead.  Prunes unwanted directories before descending, avoiding
    traversal of large subtrees (e.g. .git, node_modules) entirely.
    """
    result: list[Path] = []
    try:
        for entry in os.scandir(search_dir):
            if entry.is_dir(follow_symlinks=False):
                if entry.name in _SKIP_DIRS:
                    continue
                result.extend(_walk_files(Path(entry.path)))
            elif entry.is_file():
                result.append(Path(entry.path))
    except PermissionError:
        pass
    return result


def _evenly_sample(items: list, max_n: int) -> list:
    """Return up to *max_n* items evenly distributed across the list.

    When ``len(items) > max_n``, picks indices distributed from 0 to
    ``len(items)-1`` (both ends always included).  Otherwise returns
    all items.
    """
    total = len(items)
    if total <= max_n:
        return items
    indices = [
        (i * (total - 1) + (max_n - 1) // 2) // (max_n - 1)
        for i in range(max_n)
    ]
    seen: set[int] = set()
    selected = []
    for idx in indices:
        if idx < total and idx not in seen:
            seen.add(idx)
            selected.append(items[idx])
    return selected


def _keep_newest(items: list, max_n: int) -> list:
    """Return first *max_n* items (caller sorts newest-first).

    Used when ``context_control="time"`` to drop older results instead
    of evenly sampling across the full time range.
    """
    return items[:max_n]


def _match_paths(search_dir: Path, pattern: str | None) -> list[Path]:
    """Collect file paths under *search_dir*, optionally filtered by regex."""
    files = _walk_files(search_dir)
    if not pattern or not pattern.strip():
        return files
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from e
    return [p for p in files if compiled.search(str(p.relative_to(search_dir)))]


# ------------------------------------------------------------------
#  File collection — step 1: find files by path pattern
# ------------------------------------------------------------------

async def _collect_files_rg(
    rg_path: Path,
    pattern: str,
    directory: Path,
) -> list[tuple[str, float]]:
    """Collect files matching *pattern* via ripgrep.

    Args:
        rg_path: Absolute path to the ripgrep binary.
        pattern: Regex pattern matched against file paths.
        directory: Resolved directory to search in.

    Returns:
        List of ``(path_string, mtime)`` tuples sorted by mtime descending.
        Empty list signals a non-recoverable ripgrep error (caller falls
        back to pure Python).
    """
    cmd_files: list[str] = [
        str(rg_path), "--files", "--hidden", "--no-ignore", str(directory),
    ]

    if not pattern.strip():
        proc = await asyncio.create_subprocess_exec(
            *cmd_files,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await proc.communicate()

        if proc.returncode is not None and proc.returncode >= 2:
            return []

        text = stdout.decode("utf-8", errors="replace").strip()
    else:
        proc_files = await asyncio.create_subprocess_exec(
            *cmd_files,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout1, _stderr1 = await proc_files.communicate()

        if proc_files.returncode is not None and proc_files.returncode >= 2:
            return []

        file_list = stdout1.decode("utf-8", errors="replace")
        if not file_list.strip():
            return []

        cmd_filter: list[str] = [
            str(rg_path), "-i", "--no-line-number", "--no-heading", pattern,
        ]
        proc_filter = await asyncio.create_subprocess_exec(
            *cmd_filter,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout2, _stderr2 = await proc_filter.communicate(
            input=file_list.encode("utf-8"),
        )

        if proc_filter.returncode is not None and proc_filter.returncode >= 2:
            return []

        text = stdout2.decode("utf-8", errors="replace").strip()

    results: list[tuple[str, float]] = []
    for raw_line in text.splitlines():
        filepath = raw_line.strip()
        if not filepath:
            continue
        try:
            mtime = os.path.getmtime(filepath)
        except OSError:
            mtime = 0.0
        results.append((filepath, mtime))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def _collect_files_py(
    pattern: str,
    directory: Path,
) -> list[tuple[str, float]]:
    """Collect files matching *pattern* via pure Python.

    Args:
        pattern: Regex pattern matched against file paths.
        directory: Resolved directory to search in.

    Returns:
        List of ``(path_string, mtime)`` tuples sorted by mtime descending.
    """
    candidates = _match_paths(directory, pattern.strip() or None)

    results: list[tuple[str, float]] = []
    for p in candidates:
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            mtime = 0.0
        results.append((str(p), mtime))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


async def _collect_files(
    pattern: str,
    path: str,
) -> list[tuple[str, float]]:
    """Collect files matching path regex pattern.

    Uses ripgrep when the bundled binary is available; falls back to
    pure Python otherwise.

    Args:
        pattern: Regex pattern matched against file paths.
        path: Directory to search in, or a specific file.

    Returns:
        List of ``(path_string, mtime)`` tuples sorted by mtime descending.
    """
    search_dir = Path(path).resolve()

    if not search_dir.exists():
        return []
    if search_dir.is_file():
        try:
            mtime = os.path.getmtime(search_dir)
        except OSError:
            mtime = 0.0
        return [(str(search_dir), mtime)]

    rg_path = _get_rg_path()
    if rg_path is not None:
        try:
            return await _collect_files_rg(rg_path, pattern, search_dir)
        except Exception:
            pass
    return _collect_files_py(pattern, search_dir)


# ------------------------------------------------------------------
#  Path output formatting
# ------------------------------------------------------------------

def _format_path_results(
    files: list[tuple[str, float]],
    context_control: str,
) -> str:
    """Format file path list with optional truncation.

    Args:
        files: List of ``(path_string, mtime)`` sorted by mtime descending.
        context_control: Truncation strategy — ``"sample"`` or ``"time"``.
    """
    total = len(files)
    if total == 0:
        return "No files found"

    truncated = total > MAX_RESULTS
    if context_control == "time":
        work = _keep_newest(files, MAX_RESULTS)
    else:
        work = _evenly_sample(files, MAX_RESULTS)

    output = [p for p, _ in work]

    if truncated:
        output.append("")
        if context_control == "time":
            output.append(
                f"(Results truncated: showing {MAX_RESULTS} newest "
                f"from {total} total results. "
                "Note: results omit older files — "
                "use context_control='sample' for structural coverage.)"
            )
        else:
            output.append(
                f"(Results truncated: showing {MAX_RESULTS} evenly sampled "
                f"from {total} total results. "
                "Note: results are not time-ordered — "
                "use context_control='time' for chronological order. "
                "Consider using a more specific path or pattern.)"
            )

    return "\n".join(output)


# ------------------------------------------------------------------
#  Content search — step 2: grep within matched files
# ------------------------------------------------------------------

async def _grep_files_rg(
    rg_path: Path,
    content_pattern: str,
    file_paths: list[str],
) -> list[tuple[str, int, str]]:
    """Search *content_pattern* in *file_paths* via ripgrep.

    Args:
        rg_path: Absolute path to the ripgrep binary.
        content_pattern: Regex pattern to search for in file contents.
        file_paths: List of absolute file paths to search in.

    Returns:
        List of ``(filepath, line_number, line_text)`` tuples.
    """
    if not content_pattern.strip() or not file_paths:
        return []

    cmd: list[str] = [
        str(rg_path),
        "-i",
        "--hidden",
        "--no-ignore",
        "--line-number",
        "--no-heading",
        "--with-filename",
        "--no-pcre2",
        content_pattern,
        *file_paths,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await proc.communicate()

    if proc.returncode is not None and proc.returncode >= 2:
        return []

    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return []

    matches: list[tuple[str, int, str]] = []
    for raw_line in text.splitlines():
        raw_line = raw_line.rstrip("\n")
        # Regex anchors on the ":lineno:" field, so colons in the matched
        # line text are preserved and the Windows drive letter in the path
        # (e.g. C:\foo\bar.py:42:text) is handled correctly.
        parsed = re.match(r"^(.*):(\d+):(.*)$", raw_line)
        if not parsed:
            continue
        filepath, lineno_str, line_text = parsed.groups()
        matches.append((filepath, int(lineno_str), line_text))

    return matches


def _grep_files_py(
    content_pattern: str,
    file_paths: list[str],
) -> list[tuple[str, int, str]]:
    """Search *content_pattern* in *file_paths* via pure Python.

    Args:
        content_pattern: Regex pattern to search for in file contents.
        file_paths: List of absolute file paths to search in.

    Returns:
        List of ``(filepath, line_number, line_text)`` tuples.
    """
    if not content_pattern.strip() or not file_paths:
        return []

    try:
        compiled = re.compile(content_pattern, re.IGNORECASE)
    except re.error:
        return []

    matches: list[tuple[str, int, str]] = []
    for filepath in file_paths:
        try:
            with open(filepath, "rb") as f:
                if b"\0" in f.read(1024):
                    continue
                f.seek(0)
                for line_num, line_raw in enumerate(f, start=1):
                    line = line_raw.decode("utf-8", errors="replace")
                    if compiled.search(line):
                        matches.append((filepath, line_num, line.rstrip("\n")))
        except OSError:
            continue

    return matches


async def _grep_files(
    content_pattern: str,
    file_paths: list[str],
) -> list[tuple[str, int, str]]:
    """Search content regex within specific files.

    Uses ripgrep when the bundled binary is available; falls back to
    pure Python otherwise.

    Args:
        content_pattern: Regex pattern to search for in file contents.
        file_paths: List of absolute file paths to search in.
    """
    rg_path = _get_rg_path()
    if rg_path is not None:
        try:
            return await _grep_files_rg(rg_path, content_pattern, file_paths)
        except Exception:
            pass
    return _grep_files_py(content_pattern, file_paths)


# ------------------------------------------------------------------
#  Content output formatting
# ------------------------------------------------------------------

def _format_content_results(
    matches: list[tuple[str, int, str]],
    context_control: str,
) -> str:
    """Format content matches with mtime-based sorting and truncation.

    Args:
        matches: List of ``(filepath, line_number, line_text)`` tuples.
        context_control: Truncation strategy — ``"sample"`` or ``"time"``.
    """
    if not matches:
        return "No matches found"

    mtime_cache: dict[str, float] = {}
    unique_files = sorted({m[0] for m in matches})
    for fpath in unique_files:
        try:
            mtime_cache[fpath] = os.path.getmtime(fpath)
        except OSError:
            mtime_cache[fpath] = 0.0

    scored: list[tuple[str, int, str, float]] = [
        (fp, ln, txt, mtime_cache[fp]) for fp, ln, txt in matches
    ]
    scored.sort(key=lambda x: x[3], reverse=True)

    total = len(scored)
    truncated = total > MAX_RESULTS
    if context_control == "time":
        scored = _keep_newest(scored, MAX_RESULTS)
    else:
        scored = _evenly_sample(scored, MAX_RESULTS)

    summary_label = "newest" if context_control == "time" else "evenly sampled"
    output = [
        f"Found {total} matches"
        + (f" (showing {MAX_RESULTS} {summary_label})" if truncated else "")
    ]

    current = ""
    for filepath, line_num, text_line, _ in scored:
        if current != filepath:
            if current != "":
                output.append("")
            current = filepath
            output.append(f"{filepath}:")
        truncated_line = (
            text_line
            if len(text_line) <= MAX_LINE_LENGTH
            else text_line[:MAX_LINE_LENGTH] + "..."
        )
        output.append(f"  Line {line_num}: {truncated_line}")

    if truncated:
        hidden = total - MAX_RESULTS
        output.append("")
        if context_control == "time":
            output.append(
                f"(Results truncated: showing {MAX_RESULTS} newest "
                f"from {total} matches ({hidden} hidden). "
                "Note: results omit older matches — "
                "use context_control='sample' for structural coverage.)"
            )
        else:
            output.append(
                f"(Results truncated: showing {MAX_RESULTS} evenly sampled "
                f"from {total} matches ({hidden} hidden). "
                "Note: results are not time-ordered — "
                "use context_control='time' for chronological order. "
                "Consider using a more specific path or pattern.)"
            )

    return "\n".join(output)


# ------------------------------------------------------------------
#  Public entry point
# ------------------------------------------------------------------

async def run(
    pattern: str,
    path: str,
    content: str | None = None,
    context_control: str = "sample",
) -> str:
    """Search files by path pattern, optionally filtering by content regex.

    Always searches file paths first via *pattern* (regex matched against
    relative file/directory paths).  When *content* is provided, further
    filters the path-matched files by searching their contents for the
    content regex pattern.

    Args:
        pattern: Required. Regex pattern matched against file/directory paths.
        path: Required. Directory to search in, or a specific file.
        content: Optional. Regex pattern to search within the contents of
            path-matched files.  Returns full match output (file:line:text).
        context_control: Truncation strategy when results exceed 100.
            ``"sample"`` (default) evenly distributes selections across the
            full result set for structural coverage.  ``"time"`` keeps the
            100 newest results and drops older ones.
    """
    try:
        if not path:
            return json.dumps(
                {"error": "path is required — specify a target directory or file"}
            )
        if not pattern:
            return json.dumps(
                {"error": "pattern is required — must be a regex to match file paths"}
            )
        if context_control not in ("sample", "time"):
            return json.dumps(
                {
                    "error": (
                        f"Unknown context_control: {context_control!r}. "
                        "Valid values: sample, time."
                    )
                }
            )

        search_dir = Path(path).resolve()
        if not search_dir.exists():
            return json.dumps({"error": f"Path not found: {search_dir}"})

        files = await _collect_files(pattern, path)

        if not files:
            return "No files found"

        if content:
            file_paths = [f for f, _ in files]
            matches = await _grep_files(content, file_paths)
            return _format_content_results(matches, context_control)
        else:
            return _format_path_results(files, context_control)

    except Exception:
        return json.dumps({"error": traceback.format_exc()})


if __name__ == "__main__":
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({"error": "No input received on stdin — expected JSON args"}))
            sys.exit(1)
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)
    try:
        if not isinstance(args, dict):
            print(
                json.dumps(
                    {"error": f"Input must be a JSON object, got {type(args).__name__}"}
                )
            )
            sys.exit(1)
        kwargs = {k: v for k, v in args.items() if v is not None}
        result = asyncio.run(run(**kwargs))
        print(result)
    except TypeError as e:
        print(json.dumps({"error": f"Unexpected input arguments: {e}"}))
        sys.exit(1)
