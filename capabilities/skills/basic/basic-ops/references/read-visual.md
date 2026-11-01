# read_file — visual pipeline and standalone images

`read_file` for images and for anything the model must *see*: `mode=image`
(PNG, JPG, GIF, WebP, BMP) and the visual policy behind it. For PDFs
(`pdf-image`, `pdf-ocr`) see `read-pdf.md`; it repeats the parts you need in
PDF terms, so you do not have to open this file as well.

`mode` and `file_path` are required — there is no default `mode`.

**WARNING: visual modes are compute-heavy and expensive. Use them only when the
model genuinely needs to see the image content, or needs OCR. Never use them for
simple text extraction — use a text mode instead.**

## The core idea

Vision is the most expensive input you can consume. A single rendered page at
high DPI costs thousands of image tokens — orders of magnitude more than the
equivalent text. The visual submodes are **rungs on a ladder**, cheapest to
most expensive. Each rung answers a class of question: climbing higher than
necessary wastes budget, staying too low fails to answer.

Treat every read as a cost decision: ask "what is the cheapest rung that answers
*this specific* question?" before making the call.

## The rungs

| Level | mode + submode | Cost | What it answers |
|---|---|---|---|
| 0 | `pdf-text` | text (free) | "Is there a text layer? What does it literally say?" |
| 1 | `pdf-ocr` `full` · `image` `ocr` | OCR (cheap) | "What are the words in this (scanned) content?" |
| 2 | `pdf-image` `thumbnail` · `image` `thumbnail` | low-res vision | "What is the broad layout? Which page/region matters?" |
| 3 | `pdf-image` `cropping` · `image` `cropping` | small hi-res vision | "What is in this specific region, in detail?" |
| 3.5 | `pdf-ocr` `cropping` | OCR on a slice | "What text is in this slice of a large drawing/table?" |
| 4 | `pdf-image` `full` · `image` `full` | full vision | "What is the complete page/image, exactly?" |

## Methodology and mindset

1. **Always start low, escalate on evidence of insufficiency.** Run the cheapest
   rung that could plausibly answer; move up only when it demonstrably falls short.
2. **`full` is a one-time cost, not a habit.** Use it once to confirm layout and
   establish a coordinate anchor, then read details via `cropping`. Do not
   re-read full pages repeatedly.
3. **Separate "where" from "what".** `thumbnail` locates (which page/region),
   `cropping` extracts (the detail), `full` confirms (the structure). Never use
   an expensive rung to answer a cheap question.
4. **Text before vision.** If a text mode returns meaningful text that answers
   the question, stop — never spend image tokens.
5. **OCR is a token offloader for textual questions**, not a substitute for
   spatial understanding. Use it when the target is words (scanned text, cell
   values, labels). Do not OCR to understand layout, diagrams, colour, or geometry.
6. **For drawings and tables, prefer crop.** The signal is localized; `full`
   wastes tokens on whitespace and irrelevant regions.
7. **Respect the 3000×3000 cap.** See below.

## Canonical workflow for a document

1. **Probe** — `pdf-text`. If the text answers the question, stop.
2. **Orient** — `pdf-image` `thumbnail` for page count, layout, and where the
   interesting content lives.
3. **Anchor** — read **one** `full` page (the most representative) to understand
   layout and establish `bbox` coordinates.
4. **Extract** — `cropping` (`pdf-image`/`image` for visual, `pdf-ocr` for text)
   on the identified region at a suitable `dpi`.
5. **Escalate only if needed** — expand the `bbox`, or return to `full` to
   re-confirm layout. Never as a default.

## Decision table

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
| How big would the output image be? | `pdf-image` / `image` `test-resolution` |

## mode=image

Returns an image to the model as a multimodal user message, or OCRs it.
`submode` selects effort:

| submode | Behaviour |
|---|---|
| `full` | return as-is; optional `dpi` resample on a 72-dpi baseline (72 = original, 150 ≈ 2×). Default |
| `ocr` | send the image to the OCR server, return text as markdown. Prefer this over reading directly when only text matters |
| `thumbnail` | resize to `thumb_size` longest side (low-res glance) |
| `cropping` | slice `bbox` and return that region |
| `test` | probe OCR server availability |
| `test-resolution` | report the output size for `target` |

Image modes are **not** supported by `convert=true`, and are not subject to the
text output caps.

## Parameters

| Parameter | Applies to | Notes |
|---|---|---|
| `submode` | visual modes | Effort level. Defaults: `pdf-image`="full", `pdf-ocr`="full", `image`="full" |
| `dpi` | `pdf-image`, `pdf-ocr`, `image` | Render/resample resolution. Default 150; 72-dpi baseline for `image` |
| `bbox` | `cropping` submodes | Normalized crop region, see below |
| `thumb_size` | `image` `thumbnail` | Longest side in px, default 500 |
| `target` | `test-resolution` | Real submode to size: `full` \| `cropping` \| `thumbnail` |
| `pages` | `pdf-image`, `pdf-ocr` | Page selection; not used for standalone images |

### bbox

Normalized fractions of image width and height, top-left origin:
`[x0, y0, x1, y1]`, each value 0–1. `[0.1, 0.2, 0.6, 0.5]` selects 10%→60% of
width and 20%→50% of height. Resolution-independent — reuse the same values at
any `dpi`. Coordinates are clipped to the image bounds.

### The 3000×3000 cap

Every image returned by `pdf-image` and `image` is capped at 3000×3000 px
(proportional downscale if exceeded). Never request or rely on an image larger
than that — oversized images fail in the VLM. Thumbnails are already small.
`test-resolution` reports the final, clamped size; prefer a `dpi` whose output
stays inside the cap, and verify with `test-resolution` before fetching.

## OCR service

The OCR endpoint is set in the project's `config/config.yaml` under `basic_ops` →
`ocr_url`. If the section or key is absent the scripts fall back to
`http://localhost:3334/ocr`. Probe it with `mode=pdf-ocr` `submode=test` or
`mode=image` `submode=test` before relying on OCR.

## Examples

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "full", "dpi": 72}
```
Result: image sent to the LLM as a multimodal user message. `dpi` optionally
resamples (72 = original, 150 ≈ 2×). The tool result card shows "Image read — sent
as user message".

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "ocr"}
```
Result: image sent to the OCR server, returned as formatted markdown text.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "thumbnail", "thumb_size": 500}
```
Result: image resized to 500 px longest side, sent as a user message.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "cropping", "bbox": [0.2, 0.1, 0.9, 0.8], "dpi": 150}
```
Result: the region 20%→90% width, 10%→80% height sent as a user message.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "test"}
```
Result: `{"available": true, "status": 200, "latency_ms": 12}` — OCR server availability.

```json
{"file_path": "/home/user/photo.jpg", "mode": "image", "submode": "test-resolution", "target": "full"}
```
Result: `{"results": [{"width": 3024, "height": 4032, "clamped": true, "final_width": 2250, "final_height": 3000}]}` —
the full image would be downscaled to fit within 3000×3000.
