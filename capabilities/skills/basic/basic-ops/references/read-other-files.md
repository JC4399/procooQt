# read_file — other file types (docx, pptx, xlsx) and convert to text

Text modes of `read_file`: fast, local, return formatted text with cat-n style
line numbers. `mode` and `file_path` are required — there is no default `mode`.

Plain text files (`mode=text`) are documented in `SKILL.md`; the block is
repeated here so this file stands alone.

## mode=text

Returns file content with cat-n style line numbers (right-aligned number + tab +
content). Optional line-range slicing via `offset` / `limit`.

## mode=docx

Extracts text from DOCX files using python-docx (fast, local). Output includes
cat-n style line numbers and supports `offset` / `limit`.

## mode=pptx

Extracts text from PPTX/PPT files using python-pptx (fast, local). Output
includes cat-n style line numbers, slides delimited by Markdown headings, and
supports `offset` / `limit`.

## mode=xlsx

Reads XLSX files via openpyxl, returning the selected sheet as CSV text with line
numbers. Defaults to the first sheet. When the workbook has multiple sheets, a
header is prepended listing all sheet names and indicating which sheet is shown.

- `sheet` — sheet name to read; omit for the first sheet.
- Only the selected sheet is written by `convert=true`.

## Slicing and output caps

`offset` — 1-indexed start line. `limit` — maximum lines to return.

Text modes (with `convert=false`) are capped at 500 lines or 15,000 characters,
whichever is hit first. When either limit is exceeded a header is prepended:

```
(Result limited to first 500 lines. Selected portion has 3500 lines total.)
```

For large files make multiple `read_file` calls with `offset`/`limit` to read in
chunks. Image modes (`image`, `pdf-image`) and `pdf-ocr` are not capped.

## Convert to text

`convert=true` persists the extracted content to a .txt file and returns only a
success message — no content is shown.

- Works with the text modes: `text`, `pdf-text`, `docx`, `pptx`, `xlsx`, and `pdf-ocr`.
- **Not supported** for the image modes (`image`, `pdf-image`).
- Output is written to `{stem}.txt` alongside the input file by default; use
  `output_dir` for a different destination directory.
- For `xlsx`, only the selected `sheet` is converted.
- **Always read the file first** (`convert=false`, the default) to verify it
  contains the content you want before committing to a conversion.
- Do not shell out to `pdftotext`/`antiword` or pipe extraction output to a file —
  `convert=true` is the supported path.

## Examples

```json
{"file_path": "/home/user/example.py", "mode": "text", "offset": 1, "limit": 500}
```
Result: file contents with cat-n style line numbers. `offset`/`limit` slice the
range; `convert=false` returns content inline; `output_dir` is only used when
`convert=true`.

```json
{"file_path": "/home/user/report.docx", "mode": "docx", "offset": 10, "limit": 30}
```
Result: lines 10-39 of the extracted DOCX text.

```json
{"file_path": "/home/user/slides.pptx", "mode": "pptx", "offset": 1, "limit": 500}
```
Result: extracted PPTX text, slides delimited by Markdown headings.

```json
{"file_path": "/home/user/data.xlsx", "mode": "xlsx", "sheet": "Budget", "offset": 1, "limit": 500}
```
Result: CSV text of the "Budget" sheet with line numbers. Omit `sheet` for the
first sheet. If the workbook is multi-sheet, a header lists all sheets.

```json
{"file_path": "/home/user/data.xlsx", "mode": "xlsx", "sheet": "Summary", "convert": true, "output_dir": "/tmp/out"}
```
Result: "Converted: /home/user/data.xlsx -> /tmp/out/data_Summary.txt (987 chars)"

```json
{"file_path": "/home/user/report.docx", "mode": "docx", "convert": true, "output_dir": "/tmp/out"}
```
Result: "Converted: /home/user/report.docx -> /tmp/out/report.txt (12345 chars)"
