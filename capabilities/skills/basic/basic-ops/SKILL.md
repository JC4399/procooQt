---
name: basic-ops
description: Core file operations and script execution for everyday development tasks. Read, create, edit, and delete files. Search by regex path pattern (file/directory paths) or regex content pattern (file contents). Execute Python code or shell commands with safety guards. Also read documents, PDFs, and images through a cost-aware visual pipeline (text extraction, OCR, thumbnails, region cropping, and full rendering). Use whenever performing any file manipulation, code search, terminal operations, or reading PDFs / images / documents — even if the user doesn't explicitly ask for a specific tool name. Also store and retrieve records and text as a searchable database — initialise a records database with `init_db`, and add, search (hybrid keyword + semantic), modify, and delete records with `access_db`. Use whenever the agent needs to store document text, index a corpus or archive, record sections of documents, or search stored records by meaning or keyword, even if the user does not name a database.
---

# File Tools

You have access to the following tools:

- `read_file` — Read file contents with optional line range. Also supports document reading for PDF, DOCX, PPTX, and XLSX via dedicated modes, plus PDF OCR, PDF/image rendering, thumbnails, and region cropping. Dispatched via `mode` parameter (text / pdf-text / docx / pptx / xlsx / pdf-image / pdf-ocr / image) with an effort-level `submode` for visual modes. Use `convert=true` to persist the extracted content to disk as .txt
- `edit_file` — Create, edit, or delete files. Dispatched via `mode` parameter (create / edit / delete)
- `search_dir` — Fast file search via regex path pattern, with optional content filter as second layer (ripgrep-backed for speed). Always path-first; content regex is an optional second-layer filter on matched files
- `execute_script` — Execute Python code, shell commands, or a skill script. Dispatched via `mode` parameter (python / shell / skill)
- `init_db` — Create an empty records database (SQLite) at a given path
- `access_db` — Access a skill's records database. Dispatched via `mode` parameter (add / search / modify / delete)

## General Policy

### Tool Calling Format

You MUST call tools using the structured tool-calling mechanism provided by the API. Do NOT output XML, JSON, or any text-based tool call syntax in your response content.

### Tool Selection Policy

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

### Calling a Skill Script

To invoke an on-demand skill's script (a script not registered as a tool), use `execute_script` `mode=skill`, passing the script's absolute path as `script` and its arguments as a JSON `params` object. The harness serialises `params` and pipes it to the script's stdin, exactly as the tool runtime does — the JSON never passes through a shell.

**NEVER pipe JSON to a skill script through `mode=shell` (e.g. `echo '{...}' | python script.py`).** PowerShell quoting corrupts nested JSON; `mode=skill` exists precisely to avoid it.


### When to Use Create vs Edit

ALWAYS prefer edit_file mode=edit for changes to existing files. Use edit_file mode=create only for new files or complete rewrites. NEVER create new files unless explicitly required. NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the user.

---

## Visual Escalation Ladder (read this first)

### The Core Idea

Vision is the most expensive input you can consume. A single rendered page at high DPI can cost thousands of image tokens — orders of magnitude more than the equivalent text. The visual submodes in `read_file` are **rungs on a ladder**, ordered from cheapest to most expensive. Each rung answers a class of question. Climbing higher than necessary wastes budget; staying too low fails to answer.

Treat every read as a **cost decision**: ask "what is the cheapest rung that answers *this specific* question?" before making the call.

### The Rungs

| Level | Mode + submode | Cost | What it answers |
|---|---|---|---|
| 0 | `pdf-text` | text (free) | "Is there a text layer? What does it literally say?" |
| 1 | `pdf-ocr` `full` · `image` `ocr` | OCR (cheap) | "What are the words in this (scanned) content?" |
| 2 | `pdf-image` `thumbnail` · `image` `thumbnail` | low-res vision | "What is the broad layout? Which page/region matters?" |
| 3 | `pdf-image` `cropping` · `image` `cropping` | small hi-res vision | "What is in this specific region, in detail?" |
| 3.5 | `pdf-ocr` `cropping` | OCR on a slice | "What text is in this slice of a large drawing/table?" |
| 4 | `pdf-image` `full` · `image` `full` | full vision | "What is the complete page/image, exactly?" |

### Methodology & Mindset

1. **Always start low, escalate only on evidence of insufficiency.** Run the cheapest rung that could plausibly answer; move up only when it demonstrably falls short.
2. **Full is a one-time cost, not a habit.** Use `full` once to confirm layout and establish a coordinate anchor. Then read details via `cropping`. Do not re-read full pages repeatedly.
3. **Separate "where" from "what".** `thumbnail` locates (which page/region), `cropping` extracts (the detail), `full` confirms (the structure). Do not use an expensive rung to answer a cheap question.
4. **Text before vision.** If `pdf-text` returns meaningful text that answers the question, stop — never spend image tokens.
5. **OCR is a token offloader for textual questions**, not a substitute for spatial understanding. Use it when the target is words (scanned text, cell values, labels). Do not OCR to understand layout, diagrams, color, or geometry.
6. **For drawings and tables, prefer crop.** The signal is localized; `full` wastes tokens on whitespace and irrelevant regions.
7. **Respect the 3000×3000 cap.** Never request or rely on an image larger than 3000×3000 px — oversized images fail in the VLM. Use `test-resolution` to confirm size before fetching.

### Canonical Workflow

1. **Probe** — `pdf-text`. If the text answers the question, stop.
2. **Orient** — `pdf-image` `thumbnail` to see page count, layout, and where the interesting content lives.
3. **Anchor** — read **one** `full` page (the most representative) to understand layout and establish coordinates for `bbox`.
4. **Extract** — switch to `cropping` (image for visual, ocr for text) on the identified region(s) at a suitable `dpi`.
5. **Escalate only if needed** — expand the `bbox` or return to `full` to re-confirm layout, never as a default.

### Decision Table

| Question | Use |
|---|---|
| Is there text? What does it literally say? | `read_file` `mode=pdf-text` |
| Scanned doc / image, only need the words | `pdf-ocr` `full` / `image` `ocr` |
| Document overview: page count, layout, where content lives | `pdf-image` `thumbnail` |
| Full-page layout, exact position, confirm structure | `pdf-image` `full` |
| A table region, drawing detail, specific cell | `pdf-image` `cropping` |
| A text slice inside a large drawing/table (location known) | `pdf-ocr` `cropping` |
| Text inside a standalone image | `image` `ocr` |
| Part of an image in detail | `image` `cropping` |
| Is the OCR server up? | `pdf-ocr` `test` / `image` `test` |
| How big would the output image be? | `pdf-image`/`image` `test-resolution` |

---

## read_file

read_file dispatches on the ``mode`` parameter.

### Modes

#### Text Modes (fast, local; return formatted text)

- **mode="text"** (default): Returns file content with cat -n style line numbers (right-aligned number + tab + content) and optional line-range slicing via ``offset``/``limit``.

- **mode="pdf-text"**: Extracts text from PDF files using PyMuPDF (fast, local). Output includes cat -n style line numbers and supports ``offset``/``limit``.

- **mode="docx"**: Extracts text from DOCX files using python-docx (fast, local). Output includes cat -n style line numbers and supports ``offset``/``limit``.

- **mode="pptx"**: Extracts text from PPTX/PPT files using python-pptx (fast, local). Output includes cat -n style line numbers and supports ``offset``/``limit``.

- **mode="xlsx"**: Reads XLSX files via openpyxl, returning the selected sheet as CSV text with line numbers. Defaults to the first sheet. When the workbook contains multiple sheets, a header is prepended listing all sheet names and indicating which sheet is shown.

#### Visual Modes (compute-heavy / OCR; select effort via `submode`)

**WARNING: compute-heavy and expensive — only use when the model genuinely needs to *see* the image content with vision, or needs OCR. Never use these modes for simple text extraction; use the text modes above instead.**

- **mode="pdf-image"**: Renders PDF pages to images, returned via a user message so the model can process them. Effort selected by `submode`: `full` (default), `thumbnail`, `cropping`, `test-resolution`.

- **mode="pdf-ocr"**: Renders PDF pages to images and sends them to the OCR server, returning formatted markdown. Effort selected by `submode`: `full` (default), `cropping`, `test`.

- **mode="image"**: Reads an image file (PNG, JPG, GIF, WebP, BMP) and returns it via a user message, or OCRs it. Effort selected by `submode`: `full` (default), `ocr`, `thumbnail`, `cropping`, `test`, `test-resolution`.

### Parameters

```yaml
# read_file parameters
file_path:    # required · string
    Absolute path to the file.
mode:         # optional · string (default: "text")
    text | pdf-text | docx | pptx | xlsx | pdf-image | pdf-ocr | image
submode:      # optional · string (visual modes only)
    Effort level. Defaults: pdf-image="full", pdf-ocr="full", image="full".
pages:        # optional · string (pdf-image / pdf-ocr)
    Page selection, e.g. "1", "2-5", "1,3,5-7". Default "1"; all pages for thumbnail.
dpi:          # optional · integer (default: 150)
    Render/resample resolution.
bbox:         # optional · array [x0, y0, x1, y1] (cropping)
    Crop region as fractions of width/height, top-left origin.
thumb_size:   # optional · integer (default: 500) (image thumbnail)
    Longest side of the thumbnail in px.
target:       # optional · string (test-resolution)
    Real submode to report size for: full | cropping | thumbnail.
convert:      # optional · boolean (default: false)
    Persist extracted text to {stem}.txt and return only a success message.
sheet:        # optional · string (xlsx)
    Sheet name (default: first sheet).
offset:       # optional · integer (text modes)
    1-indexed start line.
limit:        # optional · integer (text modes)
    Maximum lines to return.
output_dir:   # optional · string (convert)
    Destination directory for the .txt.
```

### Submode Reference

**`pdf-image`**
- `thumbnail` — 500×500 grid thumbnails (up to 16 per grid) with page labels. `pages` optional; `dpi`/`bbox` ignored. Survey a document cheaply.
- `full` — render selected pages at `dpi` (default page `"1"`). Use once to confirm layout / anchor coordinates.
- `cropping` — render each selected page at `dpi`, then slice `bbox`. Read a region (table/drawing detail) in high fidelity.
- `test-resolution` — return the output pixel size for `target` without producing the image.

**`pdf-ocr`**
- `full` — OCR whole pages (default page `"1"`). For scanned/text-image PDFs where only words matter.
- `cropping` — render at `dpi`, crop `bbox`, OCR the slice. For a text slice in a large drawing/table.
- `test` — probe the OCR server; returns availability + latency.

**`image`**
- `full` — return as-is (optional `dpi` resample, 72-dpi baseline). Default.
- `ocr` — send the image to the OCR server; returns text. Prefer over reading directly when only text matters.
- `thumbnail` — resize to `thumb_size` longest side (low-res glance).
- `cropping` — slice `bbox` and return the region.
- `test` — probe the OCR server availability.
- `test-resolution` — report the output size for `target`.

### Bounding Box (`bbox`)

Normalized fractions, top-left origin, `[x0, y0, x1, y1]` where each value is 0–1 relative to page/image width and height. Example: `"bbox": [0.1, 0.2, 0.6, 0.5]` selects the region from 10%→60% of width and 20%→50% of height. Normalized coordinates are resolution-independent — reuse them regardless of `dpi`. Coordinates are clipped to the page bounds.

### The 3000×3000 Cap

Every image returned by `pdf-image` and `image` is capped at 3000×3000 px (proportional downscale if exceeded). Thumbnails are already small. `test-resolution` reports the final, clamped size. When choosing `dpi`, prefer a value whose output stays within 3000×3000; use `test-resolution` to verify before fetching.

### Convert to Text

Use ``convert=true`` to persist the extracted content to disk as a .txt file. When ``convert=true``, only a success message is returned — no content is shown.

- Works with text modes: text, pdf-text, docx, pptx, xlsx, and pdf-ocr.
- **Not supported** for image modes (image, pdf-image).
- Output is written to ``{stem}.txt`` alongside the input file by default. Use ``output_dir`` to specify a different destination directory.
- For xlsx mode, only the selected sheet is converted.
- **Always read the file first** (``convert=false``, the default) to verify it contains the content you want before committing to a conversion.

### Output Caps

Output for text modes (when ``convert=false``) is capped at 500 lines or 15000 characters (whichever is hit first). When either limit is exceeded, a header is prepended:

```
(Result limited to first 500 lines. Selected portion has 3500 lines total.)
```

For large files, use multiple read_file calls with offset/limit to read in chunks (text / pdf-text / docx / pptx / xlsx mode). Image modes (image, pdf-image) and pdf-ocr are not capped.

### Examples

#### Text Modes

```json
{"file_path": "/home/user/example.py", "mode": "text", "offset": 1, "limit": 500, "convert": false, "output_dir": "/tmp/out"}
```
Result: full file contents with cat -n style line numbers (mode="text" is default). `offset`/`limit` slice the range; `convert=false` returns content inline; `output_dir` is only used when `convert=true`.

```json
{"file_path": "/home/user/app.py", "mode": "text", "offset": 10, "limit": 30, "convert": false, "output_dir": "/tmp/out"}
```
Result: lines 10-39 of the file.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-text", "offset": 1, "limit": 500, "convert": false, "output_dir": "/tmp/out"}
```
Result: extracted PDF text with cat -n style line numbers from line 1.

```json
{"file_path": "/home/user/report.docx", "mode": "docx", "offset": 10, "limit": 30, "convert": false, "output_dir": "/tmp/out"}
```
Result: lines 10-39 of the extracted DOCX text.

```json
{"file_path": "/home/user/slides.pptx", "mode": "pptx", "offset": 1, "limit": 500, "convert": false, "output_dir": "/tmp/out"}
```
Result: extracted PPTX text (slides delimited by Markdown headings).

```json
{"file_path": "/home/user/data.xlsx", "mode": "xlsx", "sheet": "Budget", "offset": 1, "limit": 500, "convert": false, "output_dir": "/tmp/out"}
```
Result: CSV text of the "Budget" sheet with line numbers. Omit `sheet` for the first sheet. If multi-sheet, a header is prepended listing all sheets.

#### Image Modes

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "full", "dpi": 72}
```
Result: Image is sent to the LLM as a multimodal user message. `dpi` optionally resamples (72 = original, 150 = ~2x). The tool result card shows "Image read — sent as user message".

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "ocr"}
```
Result: Image is sent to the OCR server and returned as formatted markdown text.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "thumbnail", "thumb_size": 500}
```
Result: Image resized to 500px longest side and sent as a user message.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "cropping", "bbox": [0.2, 0.1, 0.9, 0.8], "dpi": 150}
```
Result: The cropped region (20%→90% width, 10%→80% height) is sent as a user message.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "test"}
```
Result: {"available": true, "status": 200, "latency_ms": 12} — OCR server availability check.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "test-resolution", "target": "full"}
```
Result: {"results": [{"width": 3024, "height": 4032, "clamped": true, "final_width": 2250, "final_height": 3000}]} — the full image would be downscaled to fit within 3000×3000.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "full", "pages": "1", "dpi": 150}
```
Result: Page 1 of the PDF rendered at 150 DPI and sent as a user message.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "full", "pages": "1-3", "dpi": 150}
```
Result: Pages 1-3 rendered at 150 DPI and sent as a user message, one per page.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "thumbnail", "pages": "1-16"}
```
Result: All pages rendered as thumbnail grids (up to 16 per image) and sent as user messages. Multi-page PDFs produce a grid preview with page numbers.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "thumbnail", "pages": "1-4,10-12"}
```
Result: Pages 1-4 and 10-12 rendered as a single 3×2 grid thumbnail.

```json
{"file_path": "/home/user/drawing.pdf", "mode": "pdf-image", "submode": "cropping", "pages": "2", "bbox": [0.3, 0.4, 0.7, 0.6], "dpi": 200}
```
Result: Page 2 rendered at 200 DPI, then the region 30%→70% width and 40%→60% height is cropped and sent as a user message.

```json
{"file_path": "/home/user/drawing.pdf", "mode": "pdf-image", "submode": "cropping", "pages": "2,3,5-7", "bbox": [0.3, 0.4, 0.7, 0.6], "dpi": 200}
```
Result: Pages 2, 3, 5, 6, 7 each rendered at 200 DPI, then the region 30%→70% width and 40%→60% height is cropped on every page and sent as a user message, one per page.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "test-resolution", "target": "full", "pages": "1", "dpi": 200}
```
Result: {"results": [{"page": 1, "width": 1700, "height": 2200, "clamped": false}]} — the output size for page 1 at 200 DPI.

#### OCR Modes

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "full", "pages": "1", "dpi": 150, "convert": false, "output_dir": "/tmp/out"}
```
Result: OCR page 1 via VLM — returns markdown, prefixed with (Page 1 of Y) so you know how many pages remain.

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "full", "pages": "1-3", "dpi": 150, "convert": false, "output_dir": "/tmp/out"}
```
Result: OCR pages 1-3, returned as combined markdown.

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "full", "pages": "1,3,5-7", "dpi": 150, "convert": false, "output_dir": "/tmp/out"}
```
Result: OCR pages 1, 3, 5, 6, 7.

```json
{"file_path": "/home/user/drawing.pdf", "mode": "pdf-ocr", "submode": "cropping", "pages": "2", "bbox": [0.3, 0.4, 0.7, 0.6], "dpi": 150}
```
Result: OCR the cropped region of page 2, returned as markdown.

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "test"}
```
Result: {"available": true, "status": 200, "latency_ms": 12} — OCR server availability check.

#### Convert to Text

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-text", "convert": true, "output_dir": "/tmp/out"}
```
Result: "Converted: /home/user/doc.pdf -> /tmp/out/doc.txt (12345 chars)"

```json
{"file_path": "/home/user/data.xlsx", "mode": "xlsx", "sheet": "Summary", "convert": true, "output_dir": "/tmp/out"}
```
Result: "Converted: /home/user/data.xlsx -> /tmp/out/data_Summary.txt (987 chars)"

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-text", "convert": true, "output_dir": "/tmp/converted"}
```
Result: "Converted: /home/user/doc.pdf -> /tmp/converted/doc.txt (12345 chars)"

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "convert": true, "output_dir": "/tmp/out"}
```
Result: "Converted: /home/user/scanned.pdf -> /tmp/out/scanned.txt (12345 chars)"

---

## edit_file

edit_file dispatches on the ``mode`` parameter.

### mode=create

Creates a new file. If the file already exists, overwrite is controlled by the ``overwrite`` flag (defaults to ``false``).

```json
{"mode": "create", "file_path": "/home/user/hello.py", "content": "print('Hello')\n"}
```
Result: "Created: /home/user/hello.py (17 bytes)"

```json
{"mode": "create", "file_path": "/home/user/hello.py", "content": "print('Updated')\n", "overwrite": false}
```
Result: "File already exists and overwrite is disabled: /home/user/hello.py"

### mode=edit

Edits an existing file using exact string matching. Rules:

- ``old_string`` must match exactly one occurrence in the file. If it matches zero times, you will receive an error. If it matches multiple times, provide more surrounding lines to make ``old_string`` unique.
- Leave ``new_string`` empty to delete the matched text.
- For editing multiple locations in a file, make separate calls per edit location.
- Use the read_file tool to examine the file before editing. You cannot edit a file you haven't read.

```json
{"mode": "edit", "file_path": "src/main.py", "old_string": "logger.info('starting')", "new_string": "logger.debug('starting')"}
```
Result: "Edited: src/main.py"

```json
{"mode": "edit", "file_path": "src/main.py", "old_string": "  pass\n  pass\n", "new_string": ""}
```
Result: "Deleted matched text from: src/main.py"

### mode=delete

Deletes a file. **Prefer trash over permanent deletion.** Moves files to system trash by default (recoverable). Set ``use_trash=false`` only when the user explicitly requests permanent deletion. Always confirm before permanently deleting files.

```json
{"mode": "delete", "file_path": "temp/cache.dat"}
```
Result: "Moved to trash: temp/cache.dat" (default: use_trash=true)

```json
{"mode": "delete", "file_path": "temp/cache.dat", "use_trash": false}
```
Result: "Permanently deleted: temp/cache.dat"

---

## search_dir

**`path` is always required** — you must specify the target directory (or a specific file).

**Use this tool INSTEAD of `find`, `grep`, `ls`, `dir`, `Get-ChildItem`, `Select-String`/`sls`, `os.walk()`, `pathlib.rglob()`, and `re.search()`/`re.match()` for any file/directory listing or content search.** Never fall back to those shell or Python commands — `search_dir` is always the correct tool for finding files by name/path or searching file contents.

The tool always searches file paths first via regex `pattern` (matched against relative file/directory paths). Optionally, a `content` regex pattern can be provided as a **second layer** to further filter the path-matched files by searching their contents.

### Parameters

| Parameter | Required | Description |
|---|---|---|
| `pattern` | yes | Regex matched against file and directory paths (case-insensitive). |
| `path` | yes | Target directory or file to search within. |
| `content` | no | Regex to search within the contents of path-matched files. Groups matches by file. |
| `context_control` | no | Truncation strategy — `"sample"` (default, evenly sampled) or `"time"` (newest first). |

### Search Strategy

**Path-first design is enforced by the tool itself** — the `pattern` parameter always searches file/directory paths. Use `content` as an additional filter to narrow results without unnecessary full-content scans.

- **Partial words** — use `chara` not `character`, `spec` not `specification`. Misspellings are common.
- **Separator wildcards** — use `.` (regex dot) for `-_., `. E.g. `test.results` matches `test-results`, `test_results`, `test.results`.
- **Tail-only IDs** — omit project prefixes. `bse.se.1003.f` not `8004MJ_CS_BSE_SE_1003-F`. `tq.st.1431` not `MCS7466-Reply-2017-TQ-ST-1431`.

### Result Limit & Context Control

Capped at **100 results**. When total exceeds 100, `context_control` controls truncation:

- **`"sample"`** (default): Results are **evenly sampled** across the full set (first and last always included) for structural coverage. **Results are not time-ordered — use `context_control="time"` when chronological order matters.**
- **`"time"`**: Keeps the **100 newest** results and drops older ones for chronological relevance. **Results omit older matches — use `context_control="sample"` when you need full-structure coverage.**

A truncation note and cross-reference reminder is appended to the output. Use a more specific path or pattern to get below the limit.

### Backend

The tool bundles ripgrep binaries for Linux (``rg``) and Windows (``rg.exe``). Both path collection and content search use ripgrep when the binary is available, with a transparent pure-Python fallback when it isn't. The tool interface and output format are identical regardless of which backend is active.

### Examples

```json
{"pattern": "\\.py$", "path": "/home/user/project"}
```
Result: list of all Python files under the directory sorted by modification time

```json
{"pattern": "src\\.*\\.ts$", "path": "/home/user/project"}
```
Result: TypeScript files matching the path pattern under the given directory

```json
{"pattern": "\\.py$", "path": "/home/user/project", "context_control": "time"}
```
Result: list of Python files, keeping newest 100 results if truncated (chronological order preserved)

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
Result: all lines containing TODO in path-matched Python files, keeping newest 100 matches (chronological order)

---

## execute_script

Dispatches on the ``mode`` parameter.

### mode=shell

Reserve for: git, npm, pip, docker, pytest, cargo and other build/test/package commands; curl, wget for network requests; any operation that genuinely requires a shell interpreter.

When installing Python packages, always use ``python -m pip install <package>`` instead of bare ``pip install <package>``. This guarantees installation into the same virtual environment that ``execute_script`` uses, so packages installed via shell mode are immediately importable in python mode.

```json
{"mode": "shell", "command": "python -m pip install requests"}
```
Result: packages installed to the correct venv

```json
{"mode": "shell", "command": "git status"}
```
Result: working tree status

```json
{"mode": "shell", "command": "rm -rf /tmp/test/"}
```
Result: "Blocked by safety guard (rm -r / rm -rf (recursive delete)): rm -rf /tmp/test/"

### mode=python

Reserve for: data processing, complex logic, API calls, computation; any task that genuinely needs a Python runtime.

```json
{"mode": "python", "code": "import json\nprint(json.dumps(sorted([3, 1, 2])))"}
```
Result: "[1, 2, 3]"

### mode=skill

Reserve for: invoking a skill's own script (typically an on-demand skill whose scripts are not registered as tools). The script must follow the skill-script contract — read one JSON object from stdin and call `run(**args)`.

- `script` — absolute path to the skill's `.py` script.
- `params` — JSON object forwarded to the script's `run(**params)`.
- `timeout` — maximum execution time in seconds (default 600).

The output is the script's stdout, returned as-is (not truncated), so a script that returns a `_media` payload is handled the same way as a registered tool.

```json
{"mode": "skill", "script": "C:/Users/me/capabilities/skills/works/update-todo-list/scripts/format_todo.py", "params": {"file_path": "C:/Users/me/Notes/26 06 Week 3.md"}}
```
Result: the script's stdout, e.g. the JSON summary of the reformatted todo list.

---

## Records database — `init_db` / `access_db`

A skill can keep a database of records: text worth retrieving later, such as the
content of previous documents, sections of legal documents, or an archive of
letters. These two tools define that database and the one way to use it, so every
database behaves the same: one schema, one API, no per-skill variation.

### The database

A database file lives at `references/<name>.db` in the consuming skill; the
caller chooses the file name (e.g. `references/uch_letter_record.db`) and passes
its absolute path as `db_path`. `init_db` creates it (an existing file is left
untouched), `access_db` reads and writes it.

The database is a single flat table of records:

| Column | Type | Purpose |
|---|---|---|
| id | integer | primary key |
| content | text | the stored record text |
| embedding | blob | vector from the embedding server, for semantic search |
| tags | text | optional comma-separated labels |
| source | text | provenance, e.g. a document or file id |
| created_at | text | ISO-8601 timestamp |
| updated_at | text | ISO-8601 timestamp |

Embeddings come from an external server at `http://localhost:3336/v1/embeddings`,
and reranking from `http://localhost:3337/v1/reranking`. Both are provided by a
llama.cpp server and live outside this skill — the tools assume the endpoints are
up. The reranker runs with a small physical batch size (~512 tokens): feeding it
a long record (or several at once) makes it return HTTP 500 "input is too large".
`access_db` does not trim the candidates; if reranking fails or every score falls
below `min_score`, hybrid falls back to the embedding (cosine) results only, so a
failure never empties the result set.

### Storing a record (`mode=add`)

When text is worth retrieving later, write it with `access_db` `mode=add`. Keep
one record to one unit of content — a document's full text, a section, a letter —
specific and self-contained, because a future agent may read it without the
document that produced it. Add a few tags naming the topic and set `source` to
the document or file id. The tool embeds the content at write time so the record
is searchable straight away.

**What to store.** Store the text itself, not a summary of what was done: the
content of a document, a section of a legal document, a past letter's wording, a
paragraph worth quoting. Do not store a working log — a record of what the agent
did this session (edits made, commands run) adds no value, because the skill or
code already reflects those changes.

### Retrieving a record (`mode=search`)

Search before answering a question the stored records should already know, with
`access_db` `mode=search`. The `submode` chooses how:

- `hybrid` (default) — keyword and semantic retrieval fused by reciprocal rank
  fusion, then reranked by the reranker. Use when unsure which signal matters.
- `keyword` — literal term matching. Use for a specific phrase.
- `semantic` — embedding similarity. Use for related meaning rather than exact
  words.

### Maintaining the database

Correct a stored record with `mode=modify`, passing only the fields that change,
and remove an obsolete one with `mode=delete`. Prefer `modify` over adding a
near-duplicate when a record has drifted from the truth. Create a fresh database
with `init_db` before a skill's first use.
