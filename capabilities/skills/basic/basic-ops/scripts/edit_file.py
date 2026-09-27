"""Tool: create, edit, or delete a file. Dispatches on the `mode` parameter."""

import asyncio
import difflib
import json
from pathlib import Path
import subprocess
import sys
import traceback


def _resolve(file_path: str) -> Path:
    return Path(file_path).resolve()


def _validate_file(path: Path, file_path: str) -> str | None:
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"
    return None


def _compute_diff(
    file_path: Path,
    original: str,
    updated: str,
) -> str:
    """Return a unified diff between original and updated content."""
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=str(file_path),
        tofile=str(file_path),
        n=3,
    )
    return "".join(lines)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _create(file_path: str, content: str, overwrite: bool) -> str:
    path = _resolve(file_path)
    existed = path.exists()

    if not overwrite and existed:
        return f"File already exists and overwrite is disabled: {file_path}"

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    action = "Overwritten" if existed else "Created"
    return f"{action}: {file_path} ({len(content)} bytes)"


async def _edit(
    file_path: str,
    old_string: str,
    new_string: str,
) -> str:
    target = _resolve(file_path)

    err = _validate_file(target, file_path)
    if err:
        return err

    with open(target, encoding="utf-8", errors="replace") as f:
        original = f.read()

    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        idx = original.find(old_string, start)
        if idx == -1:
            break
        matches.append((idx, idx + len(old_string)))
        start = idx + max(1, len(old_string))

    if not matches:
        return f"old_string not found in file: {file_path}"
    if len(matches) > 1:
        return (
            f"old_string matches {len(matches)} times in file. "
            f"Provide more surrounding context in old_string to make it unique."
        )

    start, end = matches[0]

    if (
        new_string == ""
        and not original[start:end].endswith("\n")
        and original[end : end + 1] == "\n"
    ):
        end += 1

    updated = original[:start] + new_string + original[end:]

    with open(target, "w", encoding="utf-8", errors="replace") as f:
        f.write(updated)

    diff = _compute_diff(target, original, updated)

    verb = "Deleted" if new_string == "" else "Edited"
    return f"{verb}: {file_path}\n\n{diff.rstrip()}"


async def _delete(file_path: str, use_trash: bool) -> str:
    target = _resolve(file_path)

    err = _validate_file(target, file_path)
    if err:
        return err

    if use_trash:
        trash_cmds = ["recycle", "trash", "gio", "gvfs-trash", "kioclient5", "kioclient"]
        for cmd in trash_cmds:
            try:
                if cmd == "recycle":
                    # Windows: recycle CLI
                    subprocess.run(
                        ["recycle", "--delete", str(target)],
                        check=True, capture_output=True,
                    )
                    return f"Moved to trash: {file_path}"
                if cmd == "trash":
                    subprocess.run(
                        ["trash", str(target)], check=True, capture_output=True
                    )
                elif cmd == "kioclient5":
                    subprocess.run(
                        ["kioclient5", "move", str(target), "trash:/"],
                        check=True, capture_output=True,
                    )
                elif cmd == "kioclient":
                    subprocess.run(
                        ["kioclient", "move", str(target), "trash:/"],
                        check=True, capture_output=True,
                    )
                else:
                    subprocess.run(
                        [cmd, "trash", str(target)],
                        check=True, capture_output=True,
                    )
                return f"Moved to trash: {file_path}"
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue

        # Fallback: try Windows ctypes SHFileOperation API
        import ctypes
        import platform

        if platform.system() == "Windows":
            try:
                FO_DELETE = 0x0003  # noqa: N806 - Windows API constant name
                FOF_ALLOWUNDO = 0x0040  # noqa: N806 - Windows API constant name

                class FILEOP(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", ctypes.c_void_p),
                        ("wFunc", ctypes.c_uint),
                        ("pFrom", ctypes.c_wchar_p),
                        ("pTo", ctypes.c_wchar_p),
                        ("fFlags", ctypes.c_uint),
                        ("fAnyOperationsAborted", ctypes.c_bool),
                        ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", ctypes.c_wchar_p),
                    ]

                op = FILEOP()
                op.hwnd = 0
                op.wFunc = FO_DELETE
                op.pFrom = str(target.resolve()) + '\0'
                op.pTo = None
                op.fFlags = FOF_ALLOWUNDO
                op.fAnyOperationsAborted = False
                op.hNameMappings = None
                op.lpszProgressTitle = None

                if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0:
                    return f"Moved to trash: {file_path}"
            except (AttributeError, OSError):
                pass

        return (
            "No trash command found (tried: recycle, trash, gio, gvfs-trash, "
            "kioclient5, kioclient).\n"
            "Set use_trash=false for permanent deletion, or install 'recycle' "
            "(Windows) / 'trash-cli' (Linux/macOS)."
        )

    target.unlink()
    return f"Permanently deleted: {file_path}"


async def run(
    mode: str,
    # create params
    file_path: str,
    content: str = "",
    overwrite: bool = True,
    # edit params
    old_string: str = "",
    new_string: str = "",
    # delete params
    use_trash: bool = True,
) -> str:
    """Create, edit, or delete a file based on the mode parameter.

    Args:
        mode: Operation mode — "create", "edit", or "delete".
        file_path: Target file path.
        content: (create) Full text content to write.
        overwrite: (create ONLY) Whether to overwrite if the file already exists. Defaults to true.
        old_string: (edit) Exact text to find and replace. REQUIRED for edit mode.
        new_string: (edit) Replacement text. Leave empty to delete the matched text.
        use_trash: (delete) Move to system trash instead of permanent deletion. Defaults to true.
    """
    try:
        if mode == "create":
            return await _create(file_path, content, overwrite)
        elif mode == "edit":
            if not old_string:
                return (
                    "Error: old_string is required for edit mode."
                    " Provide the exact text to find and replace."
                )
            return await _edit(file_path, old_string, new_string)
        elif mode == "delete":
            return await _delete(file_path, use_trash)
        else:
            return f"Unknown mode: {mode}. Valid modes: create, edit, delete."
    except Exception:
        return json.dumps({"error": traceback.format_exc()})


if __name__ == "__main__":
    args = json.loads(sys.stdin.read())
    result = asyncio.run(run(**{k: v for k, v in args.items() if v is not None}))
    sys.stdout.reconfigure(encoding="utf-8")
    print(result)
