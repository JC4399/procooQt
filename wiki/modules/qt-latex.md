# qt.latex — in-memory LaTeX math → data-URI images

Source: `src/qt/latex.py`

## Purpose

Rasterise LaTeX math spans to PNG images that are held **purely in memory** and
embedded into the response card's rich-text HTML as `data:` URIs. The browser
surface for this is
[`qt.markdown`](qt-markdown.md): only response bodies run through
`render_markdown`, so math rendering is effectively response-card-only.

There is no cache directory and no file I/O: because `ChatListModel` is a
*derived* render plan and the rendered HTML is never persisted, the LaTeX source
in `chat.messages` is simply re-rendered on load. Nothing has to be pruned or
kept in sync with the chat/session lifecycle. `matplotlib.mathtext` supplies the
LaTeX subset (no TeX distribution is required), configured with the Computer
Modern font set, a transparent background, and glyphs coloured by
[`COLOR_MD_MATH`](qt-theme.md). Because mathtext implements only a subset of
LaTeX, `\boxed{…}` (unsupported by mathtext) is emulated by stripping the wrapper
before typesetting and drawing the rectangle afterwards.

matplotlib is not thread-safe, so rasterisation is serialised behind a module
lock; renders happen on `asyncio.to_thread` workers because
`ChatController._compute_render_plan` runs off the GUI thread.

## Deliverables

- `render_math_fragment(latex, *, display) -> str` — an `<img>` fragment backed
  by a `data:` URI, or `""` on failure.
- `MathImage` — frozen dataclass of `uri`, `width`, `height`.
- `_render_math_image` / `_build_math_image` / `_render_png` / `_png_size` /
  `_logical_size` — memo lookup, rasterisation, and size conversion helpers.
- `_strip_boxed` / `_draw_box` — `\boxed` emulation (strip the wrapper for
  mathtext, then draw the rectangle).
- Module state `_MEMO` (bounded LRU), `_MEMO_LOCK`, `_RENDER_LOCK`,
  `_MATPLOTLIB_READY`.

## Steps / Flow

### `render_math_fragment`

1. Look up `_render_math_image(latex, display)`.
2. If it returns `None` (empty source or parse failure), return `""` so the
   markdown renderer can fall back to the literal source.
3. Otherwise return
   `<img src="{uri}" width="{width}" height="{height}">`.

### `_render_math_image` (memo)

1. Reject a blank source (`None`).
2. On an `(latex, display)` memo hit, move the entry to the MRU end and return it.
3. Otherwise build the image outside the memo lock, then insert it, move to MRU,
   and evict the least-recently-used entry while `len(_MEMO) > _MEMO_MAX`.
   Success **and** failure (`None`) are memoised, so an invalid expression is not
   retried on every streaming tick.

### `_render_png` (rasterisation)

1. Lazily configure matplotlib on first use: `use("Agg")` and
   `rcParams["mathtext.fontset"] = "cm"`.
2. Create a bare `Figure`/`FigureCanvasAgg`, place `$latex$` at the origin with
   `fontsize = FONT_SIZE_LATEX` (14 pt — deliberately larger than the 12 pt body
   so math glyphs do not read small) and `color = COLOR_MD_MATH`.
3. `savefig` PNG to a `BytesIO` with `transparent=True`,
   `bbox_inches="tight"`, `pad_inches = _PAD_DISPLAY | _PAD_INLINE`, and
   `dpi = _RENDER_DPI`.
4. Return the bytes, or log a warning and return `None` when matplotlib raises
   (this is the only catch-all in the render path — one bad expression must
   never break a card).

### Size conversion

The PNG is rasterised at `_RENDER_DPI` (192) for crispness and scaled back to
logical pixels at `_BASE_DPI` (96); `_png_size` reads the width/height straight
from the PNG `IHDR` header (no Pillow import).

### `\boxed` emulation

mathtext does not implement `\boxed`. `_strip_boxed` removes every
brace-balanced `\boxed{…}` wrapper (recursively, up to `_MAX_BOX_DEPTH`) before
typesetting, and reports whether the wrapper enclosed the **whole** expression
(no non-boxed residue). `_render_png` then calls `_draw_box`, which adds a
matplotlib `Rectangle` around the text artist's expanded display extent; because
`savefig` uses `bbox_inches="tight"`, the saved PNG is cropped around the box.
A box around only part of an expression is dropped (no rectangle) rather than
drawn in the wrong place. Commands mathtext lacks entirely (`\begin`, `\ce`,
`\pmatrix`, `\displaystyle`, …) fall through to the literal-source fallback in
[`qt.markdown`](qt-markdown.md).

## Function Reference

| Signature | Inputs | Output | Flow | Raises / Side effects |
|---|---|---|---|---|
| `def render_math_fragment(latex: str, *, display: bool) -> str` | `latex` — source without `$`; `display` — block vs inline (padding + memo key only) | `<img …>` fragment or `""` | `_render_math_image` → format | Populates the memo; renders on a miss |
| `def _render_math_image(latex: str, *, display: bool) -> MathImage \| None` | as above | Memoised image or `None` | blank check → memo hit → build → insert/evict | Mutates `_MEMO` under `_MEMO_LOCK` |
| `def _build_math_image(latex: str, *, display: bool) -> MathImage \| None` | as above | Image with `data:` URI + logical size | `_strip_boxed` → `_render_png` → `_png_size` → `_logical_size` → base64 | None |
| `def _render_png(latex: str, *, display: bool, boxed: bool) -> bytes \| None` | `latex` — wrapper-stripped source; `display`; `boxed` — draw rectangle | Transparent PNG bytes or `None` | lazy matplotlib → Figure → (`_draw_box`) → `savefig` to `BytesIO` | Serialised by `_RENDER_LOCK`; sets `_MATPLOTLIB_READY`; logs+swallows render errors |
| `def _strip_boxed(latex: str, _depth: int = 0) -> tuple[str, bool]` | `latex` — source; `_depth` — recursion guard | `(stripped, box_whole)` | Scan for brace-balanced `\boxed{…}`, recurse, track residue | Pure; no rendering |
| `def _draw_box(figure: object, text: object) -> None` | `figure` — matplotlib `Figure`; `text` — `Text` artist | `None` | Expanded window extent → figure coords → add `Rectangle` patch | Mutates the figure (adds an artist) |
| `def _png_size(png: bytes) -> tuple[int, int]` | PNG bytes | `(width, height)` pixels | read IHDR big-endian uint32 | `(1, 1)` for a truncated file |
| `def _logical_size(pixel_size: tuple[int, int]) -> tuple[int, int]` | pixel size | logical size | `_BASE_DPI / _RENDER_DPI` scale, min 1 | None |

### `MathImage`

| Field | Type | Meaning |
|---|---|---|
| `uri` | `str` | `data:image/png;base64,…` source |
| `width` | `int` | Logical width in pixels |
| `height` | `int` | Logical height in pixels |

### Module constants

| Name | Value | Purpose |
|---|---|---|
| `_RENDER_DPI` | `192` | Raster DPI (2× the logical baseline) |
| `_BASE_DPI` | `96` | Qt's logical point-to-pixel baseline |
| `_PAD_INLINE` / `_PAD_DISPLAY` | `0.03` / `0.06` | Transparent margin (inches) |
| `_BOX_LINEWIDTH` | `0.8` | Emulated `\boxed` border width (points) |
| `_BOXED_CMD` / `_MAX_BOX_DEPTH` | `\boxed` / `16` | `\boxed` wrapper token and recursion cap |
| `_MEMO_MAX` | `512` | In-memory memo bound |
| `_MEMO` | `OrderedDict` | LRU of `(latex, display) → MathImage \| None` |
| `_MEMO_LOCK` / `_RENDER_LOCK` | `threading.Lock` | Memo vs matplotlib serialisation |
| `_MATPLOTLIB_READY` | `bool` | Lazy one-time matplotlib configuration flag |

## See also

- [qt-markdown](qt-markdown.md) — parses `$…$`/`$$…$$` and calls
  `render_math_fragment` from its `math_inline`/`math_block` rules.
- [qt-theme](qt-theme.md) — `COLOR_MD_MATH` and `FONT_SIZE_MARKDOWN`.
