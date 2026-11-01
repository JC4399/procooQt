# search_dir

Fast file search: regex over file/directory **paths**, with an optional regex
content filter as a second layer. ripgrep-backed for speed.

**`path` is always required** — you must specify the target directory (or a
specific file). This tool does not take a `mode`; it takes `pattern`, `path`, and
optionally `content` and `context_control`.

**Use this tool INSTEAD of `find`, `grep`, `ls`, `dir`, `Get-ChildItem`,
`Select-String`/`sls`, `os.walk()`, `pathlib.rglob()`, and
`re.search()`/`re.match()` for any file/directory listing or content search.**
Never fall back to those shell or Python commands — `search_dir` is always the
correct tool for finding files by name/path or searching file contents.

Paths are matched first via the regex `pattern` (against relative file/directory
paths). A `content` regex is an optional second layer that filters the
path-matched files by searching their contents.

## Parameters

| Parameter | Required | Description |
|---|---|---|
| `pattern` | yes | Regex matched against file and directory paths (case-insensitive). |
| `path` | yes | Target directory or file to search within. |
| `content` | no | Regex to search within the contents of path-matched files. Groups matches by file. |
| `context_control` | no | Truncation strategy — `"sample"` (default, evenly sampled) or `"time"` (newest first). |

## Search strategy

**Path-first design is enforced by the tool itself** — `pattern` always searches
file/directory paths. Use `content` as an additional filter to narrow results
without unnecessary full-content scans.

- **Partial words** — use `chara` not `character`, `spec` not `specification`.
  Misspellings are common.
- **Separator wildcards** — use `.` (regex dot) for `-_., `. E.g. `test.results`
  matches `test-results`, `test_results`, `test.results`.
- **Tail-only IDs** — omit project prefixes. `bse.se.1003.f` not
  `8004MJ_CS_BSE_SE_1003-F`. `tq.st.1431` not `MCS7466-Reply-2017-TQ-ST-1431`.

## Result limit and context control

Capped at **100 results**. When the total exceeds 100, `context_control` controls
truncation:

- **`"sample"`** (default): results are **evenly sampled** across the full set
  (first and last always included) for structural coverage. **Not time-ordered —
  use `context_control="time"` when chronological order matters.**
- **`"time"`**: keeps the **100 newest** results and drops older ones for
  chronological relevance. **Older matches are omitted — use `"sample"` when you
  need full-structure coverage.**

A truncation note and cross-reference reminder is appended to the output. Use a
more specific path or pattern to get below the limit.

## Backend

The tool bundles ripgrep binaries for Linux (`rg`) and Windows (`rg.exe`). Both
path collection and content search use ripgrep when the binary is available, with
a transparent pure-Python fallback when it isn't. The interface and output format
are identical either way.

## Examples

```json
{"pattern": "\\.py$", "path": "/home/user/project"}
```
Result: all Python files under the directory, sorted by modification time

```json
{"pattern": "src\\.*\\.ts$", "path": "/home/user/project"}
```
Result: TypeScript files matching the path pattern under the given directory

```json
{"pattern": "\\.py$", "path": "/home/user/project", "context_control": "time"}
```
Result: Python files, keeping the newest 100 if truncated (chronological order preserved)

```json
{"pattern": "\\.py$", "path": "/home/user/project", "content": "TODO"}
```
Result: all lines containing TODO within the path-matched Python files, grouped by file

```json
{"pattern": "\\.ts$", "path": "/home/user/project", "content": "function\\s+\\w+"}
```
Result: TypeScript function definitions across the path-matched TypeScript files

```json
{"pattern": "\\.py$", "path": "/home/user/project", "content": "TODO", "context_control": "time"}
```
Result: all lines containing TODO in path-matched Python files, newest 100 matches if truncated
