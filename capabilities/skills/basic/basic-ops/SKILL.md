---
name: basic-ops
description: Core file operations and script execution for everyday development tasks. Read, create, edit, and delete files. Search by regex path pattern (file/directory paths) or regex content pattern (file contents). Execute Python code or shell commands with safety guards. Also read documents, PDFs, and images through a cost-aware visual pipeline (text extraction, OCR, thumbnails, region cropping, and full rendering). Use whenever performing any file manipulation, code search, terminal operations, or reading PDFs / images / documents — even if the user doesn't explicitly ask for a specific tool name. Also store and retrieve records and text as a searchable database — initialise a records database with `init_db`, and add, search (hybrid keyword + semantic), modify, and delete records with `access_db`. Use whenever the agent needs to store document text, index a corpus or archive, record sections of documents, or search stored records by meaning or keyword, even if the user does not name a database.
---

# File Tools

- `read_file` — read file contents and documents; plain text below, everything else routed to a reference
- `edit_file` — create, edit, delete files (`mode` create / edit / delete)
- `search_dir` — regex search over file paths, optional content filter (ripgrep-backed)
- `execute_script` — run Python code, shell commands, or another skill's script (`mode` python / shell / skill)
- `init_db` — create an empty records database (SQLite)
- `access_db` — add, search, modify, delete records (hybrid keyword + semantic)

## Tool Selection Policy

**NEVER use `execute_script` (neither shell nor python mode) for any operation that can be accomplished by the dedicated file tools (`read_file`, `edit_file`, `search_dir`).** The dedicated tools are inherently safer, provide structured output, and avoid shell injection risks.

DO NOT use execute_script for:
  cat / head / tail / less          →  use read_file
  echo / cat > / tee / touch         →  use edit_file mode=create
  sed / awk / perl -i                →  use edit_file mode=edit
  rm / unlink / rmdir                →  use edit_file mode=delete
  find / ls (for file listing)       →  use search_dir
  grep / rg (for content search)     →  use search_dir with content=...
  echo / printf (to communicate)     →  output text directly, never use shell to talk
  pdftotext / antiword etc          →  use read_file (mode=pdf-text/docx/...)
  piping extraction output to file  →  use read_file with convert=true

DO NOT use execute_script mode=shell (PowerShell) for:
  Get-Content / gc / type            →  use read_file
  Set-Content / Out-File / New-Item  →  use edit_file mode=create
  -replace operator / Set-Content    →  use edit_file mode=edit
  Remove-Item / rm / del / rmdir     →  use edit_file mode=delete
  Get-ChildItem / ls / dir           →  use search_dir
  Select-String / sls                →  use search_dir with content=...
  Write-Output / Write-Host / echo   →  output text directly, never use shell to talk
  external PDF/DOCX text extractors  →  use read_file (mode=pdf-text/docx/...)
  piping extraction output to file  →  use read_file with convert=true

DO NOT use execute_script mode=python for:
  open().read() / readlines()        →  use read_file
  open().write() / writelines()      →  use edit_file mode=create
  str.replace() / file.readlines()   →  use edit_file mode=edit
  os.remove() / pathlib.unlink()     →  use edit_file mode=delete
  os.walk() / pathlib.rglob()        →  use search_dir
  re.search() / re.match()           →  use search_dir with content=...
  document extraction + file.write()  →  use read_file with convert=true

## read_file — plain text files

`mode=text` returns file content with cat -n style line numbers (right-aligned
number + tab + content). `file_path` is absolute. `offset` (1-indexed start line)
and `limit` (maximum lines) slice the range.

```json
{"file_path": "/home/user/app.py", "mode": "text", "offset": 10, "limit": 30}
```
Result: lines 10-39 of the file.

Output is capped at 500 lines or 15000 characters, whichever comes first; when
either limit is hit a header is prepended, e.g. `(Result limited to first 500
lines. Selected portion has 3500 lines total.)` Read large files in chunks with
repeated `offset` / `limit` calls.

## References

Open the file before using what it covers. Each reference is self-contained.

| File | Open when |
|---|---|
| `references/read-pdf.md` | any PDF — text layer, OCR, page rendering, cropping, convert |
| `references/read-visual.md` | images / scanned pages; **read before any visual mode — they cost image tokens** |
| `references/read-other-files.md` | docx, pptx, xlsx, `sheet`, `convert=true` to .txt |
| `references/edit-file.md` | creating, editing, deleting a file; edit-over-create rule |
| `references/search-dir.md` | searching paths or file contents; pattern strategy, result caps |
| `references/execute-script.md` | running code or shell; calling a skill script with `params` |
| `references/records-db.md` | storing / searching a records database; embedding + rerank endpoints |
