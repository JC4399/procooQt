# edit_file

`edit_file` dispatches on the `mode` parameter: `create`, `edit`, `delete`.
`mode` and `file_path` are required — omitting `mode` raises
`TypeError: run() missing 1 required positional argument: 'mode'`.

## Which mode to pick

**ALWAYS prefer `mode=edit` for changes to existing files.** Use `mode=create`
only for new files or complete rewrites. NEVER create new files unless
explicitly required. NEVER proactively create documentation files (*.md) or
README files — only create documentation if the user explicitly asked for it.

## mode=create

Creates a new file. If the file already exists, `overwrite` controls what happens
(defaults to `false`).

```json
{"mode": "create", "file_path": "/home/user/hello.py", "content": "print('Hello')\n"}
```
Result: "Created: /home/user/hello.py (17 bytes)"

```json
{"mode": "create", "file_path": "/home/user/hello.py", "content": "print('Updated')\n", "overwrite": false}
```
Result: "File already exists and overwrite is disabled: /home/user/hello.py"

## mode=edit

Edits an existing file by exact string matching. Rules:

- `old_string` must match exactly one occurrence. Zero matches is an error; if it
  matches multiple times, include more surrounding lines to make it unique.
- Leave `new_string` empty to delete the matched text.
- For edits in several locations, make a separate call per location.
- Read the file first. You cannot edit a file you haven't read.

```json
{"mode": "edit", "file_path": "src/main.py", "old_string": "logger.info('starting')", "new_string": "logger.debug('starting')"}
```
Result: "Edited: src/main.py"

```json
{"mode": "edit", "file_path": "src/main.py", "old_string": "  pass\n  pass\n", "new_string": ""}
```
Result: "Deleted matched text from: src/main.py"

## mode=delete

Deletes a file. **Prefer trash over permanent deletion.** Files move to system
trash by default (recoverable). Set `use_trash=false` only when the user
explicitly requests permanent deletion, and always confirm before permanently
deleting files.

```json
{"mode": "delete", "file_path": "temp/cache.dat"}
```
Result: "Moved to trash: temp/cache.dat" (default: use_trash=true)

```json
{"mode": "delete", "file_path": "temp/cache.dat", "use_trash": false}
```
Result: "Permanently deleted: temp/cache.dat"
