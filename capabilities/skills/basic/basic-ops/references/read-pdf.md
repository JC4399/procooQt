# read_file — PDF

`read_file` for any PDF: `mode=pdf-text` (text layer), `mode=pdf-ocr` (OCR),
`mode=pdf-image` (rendered pages). `mode` and `file_path` are required — there is
no default `mode`, and omitting it returns an error, not a fallback.

## Pick the cheapest rung

Vision is the most expensive input you can consume. One rendered page at high DPI
costs thousands of image tokens — orders of magnitude more than the same content
as text. Before each call ask: what is the cheapest rung that answers *this
specific* question?

| Level | mode + submode | Cost | Answers |
|---|---|---|---|
| 0 | `pdf-text` | text (free) | "Is there a text layer? What does it literally say?" |
| 1 | `pdf-ocr` `full` | OCR (cheap) | "What are the words in this scanned page?" |
| 2 | `pdf-image` `thumbnail` | low-res vision | "Which page? Where does the interesting content sit?" |
| 3 | `pdf-image` `cropping` | small hi-res vision | "What is in this specific region, in detail?" |
| 3.5 | `pdf-ocr` `cropping` | OCR on a slice | "What text is in this slice of a large drawing/table?" |
| 4 | `pdf-image` `full` | full vision | "What is the complete page, exactly?" |

## Workflow

1. **Probe** — `pdf-text`. If the text answers the question, stop. Never spend
   image tokens on a question the text layer already answers.
2. **Orient** — `pdf-image` `thumbnail` over all pages: page count, layout, and
   where the interesting content lives.
3. **Anchor** — **one** `pdf-image` `full` page (the most representative) to
   confirm layout and establish `bbox` coordinates.
4. **Extract** — `cropping` on the identified region: `pdf-image` for visual
   detail, `pdf-ocr` for words inside that region. Use a suitable `dpi`.
5. **Escalate only on evidence** — widen the `bbox`, or return to `full` to
   re-confirm layout. `full` is a one-time cost, not a habit; do not re-read
   whole pages.

- **Text before vision.** `pdf-text` first, every time.
- **Separate "where" from "what".** `thumbnail` locates, `cropping` extracts,
  `full` confirms structure. Never use an expensive rung to answer a cheap question.
- **OCR offloads words**, it does not give spatial understanding. Do not OCR to
  learn layout, diagrams, colour, or geometry.
- **Drawings and tables: prefer `cropping`.** The signal is localized; `full`
  wastes tokens on whitespace and irrelevant regions.

## mode=pdf-text

Extracts text with PyMuPDF (fast, local). Cat-n style line numbers (right-aligned
number + tab + content); supports `offset` / `limit` to page through long
extracts. Subject to the text output caps below.

## mode=pdf-ocr

Renders pages to images and sends them to the OCR server, returning formatted
markdown. Output is prefixed "(Page N of Y)" so you know what remains. `submode`
selects effort:

| submode | Behaviour |
|---|---|
| `full` | OCR whole pages (default page `"1"`). For scanned or text-image PDFs where only words matter |
| `cropping` | render at `dpi`, crop `bbox`, OCR the slice. For a text slice inside a large drawing or table whose location you already know |
| `test` | probe the OCR server: `{"available": true, "status": 200, "latency_ms": 12}` |

Not subject to the text output caps. `convert=true` is supported.

## mode=pdf-image

Renders pages to images, returned as a user message so the model can see them.
Not supported with `convert`. `submode` selects effort:

| submode | Behaviour |
|---|---|
| `thumbnail` | 500×500 grid thumbnails, up to 16 per grid, with page labels. `pages` optional; `dpi` and `bbox` ignored. The cheap way to survey a document |
| `full` | render selected pages at `dpi` (default page `"1"`), one image per page. Use once, to confirm layout and anchor coordinates |
| `cropping` | render each selected page at `dpi`, then slice `bbox`. High fidelity on a region (table, drawing detail, a specific cell) |
| `test-resolution` | report the output pixel size for `target` without producing the image |

## Parameters

| Parameter | Applies to | Notes |
|---|---|---|
| `pages` | `pdf-image`, `pdf-ocr` | `"1"`, `"2-5"`, `"1,3,5-7"`. Default `"1"`; all pages for `thumbnail` |
| `dpi` | `pdf-image`, `pdf-ocr` | Render resolution, default 150 |
| `bbox` | `cropping` submodes | Normalized crop region, see below |
| `target` | `test-resolution` | The real submode to size: `full` \| `cropping` \| `thumbnail` |
| `convert` | `pdf-text`, `pdf-ocr` | **Not** supported for `pdf-image` |
| `offset` / `limit` | `pdf-text` | 1-indexed start line / maximum lines |
| `output_dir` | `convert=true` | Destination directory for the .txt |

### bbox

Normalized fractions of page width and height, top-left origin:
`[x0, y0, x1, y1]`, each value 0–1. `[0.1, 0.2, 0.6, 0.5]` selects 10%→60% of
width and 20%→50% of height. Resolution-independent — reuse the same values at
any `dpi`. Coordinates are clipped to the page bounds.

### The 3000×3000 cap

Every image returned by `pdf-image` is capped at 3000×3000 px (proportional
downscale if exceeded). Never request or rely on an image larger than that —
oversized images fail in the VLM. Pick a `dpi` whose output stays inside the cap,
and confirm with `test-resolution` before fetching. Thumbnails are already small.

## Convert to text

`convert=true` writes the extracted text to `{stem}.txt` beside the PDF (or into
`output_dir`) and returns only a success message — no content is shown. Works for
`pdf-text` and `pdf-ocr`; **not** for `pdf-image`. Read the file first with
`convert=false` to confirm it contains what you want before committing to a
conversion.

## Output caps

`pdf-text` (with `convert=false`) is capped at 500 lines or 15,000 characters,
whichever comes first, with a header prepended when either limit is hit:

```
(Result limited to first 500 lines. Selected portion has 3500 lines total.)
```

Page through with repeated `offset` / `limit` calls. `pdf-ocr` and `pdf-image` are
not capped.

## Examples

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-text", "offset": 1, "limit": 500}
```
Result: extracted PDF text with line numbers from line 1.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-text", "convert": true, "output_dir": "/tmp/out"}
```
Result: "Converted: /home/user/doc.pdf -> /tmp/out/doc.txt (12345 chars)"

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "full", "pages": "1", "dpi": 150}
```
Result: OCR of page 1 via the OCR server, as markdown, prefixed (Page 1 of Y).

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "full", "pages": "1-3", "dpi": 150}
```
Result: OCR pages 1-3 as combined markdown.

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "full", "pages": "1,3,5-7", "dpi": 150}
```
Result: OCR pages 1, 3, 5, 6, 7.

```json
{"file_path": "/home/user/drawing.pdf", "mode": "pdf-ocr", "submode": "cropping", "pages": "2", "bbox": [0.3, 0.4, 0.7, 0.6], "dpi": 150}
```
Result: OCR of the cropped region of page 2, returned as markdown.

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "submode": "test"}
```
Result: `{"available": true, "status": 200, "latency_ms": 12}` — OCR server availability.

```json
{"file_path": "/home/user/scanned.pdf", "mode": "pdf-ocr", "convert": true, "output_dir": "/tmp/out"}
```
Result: "Converted: /home/user/scanned.pdf -> /tmp/out/scanned.txt (12345 chars)"

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "full", "pages": "1", "dpi": 150}
```
Result: page 1 rendered at 150 DPI, sent as a user message.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "full", "pages": "1-3", "dpi": 150}
```
Result: pages 1-3 rendered at 150 DPI, one image per page.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "thumbnail", "pages": "1-16"}
```
Result: all pages as thumbnail grids (up to 16 per image), sent as user messages, with page numbers.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "thumbnail", "pages": "1-4,10-12"}
```
Result: pages 1-4 and 10-12 in a single 3×2 grid thumbnail.

```json
{"file_path": "/home/user/drawing.pdf", "mode": "pdf-image", "submode": "cropping", "pages": "2", "bbox": [0.3, 0.4, 0.7, 0.6], "dpi": 200}
```
Result: page 2 at 200 DPI, region 30%→70% width and 40%→60% height cropped and sent as a user message.

```json
{"file_path": "/home/user/drawing.pdf", "mode": "pdf-image", "submode": "cropping", "pages": "2,3,5-7", "bbox": [0.3, 0.4, 0.7, 0.6], "dpi": 200}
```
Result: each of pages 2, 3, 5, 6, 7 rendered at 200 DPI and cropped to the same region, one image per page.

```json
{"file_path": "/home/user/doc.pdf", "mode": "pdf-image", "submode": "test-resolution", "target": "full", "pages": "1", "dpi": 200}
```
Result: `{"results": [{"page": 1, "width": 1700, "height": 2200, "clamped": false}]}`.
