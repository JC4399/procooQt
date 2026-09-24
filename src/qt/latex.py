"""In-memory LaTeX math rendering for response-card bodies.

Renders LaTeX math spans (parsed by the ``dollarmath`` Markdown-It plugin) to PNG
images held purely in memory and embedded into the card's rich-text HTML as
``data:`` URIs. Nothing is written to disk, so there is no cache directory to
prune and no coupling to the chat/session lifecycle: the LaTeX source lives in
the persisted chat history and the image is simply re-rendered on load.

matplotlib's ``mathtext`` supplies the LaTeX subset (no TeX distribution is
required), configured with the Computer Modern font set, a transparent
background, and glyphs coloured to match the dark theme. Only response cards run
their bodies through :func:`~src.qt.markdown.render_markdown`, so this module is
reached exclusively from response bodies.

Matplotlib is not thread-safe, so rasterisation is serialised behind a module
lock; renders happen on ``asyncio.to_thread`` workers because the render plan is
computed off the GUI thread.
"""

from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import dataclass
import io
import logging
import threading
from typing import Any

from .theme import COLOR_MD_MATH, FONT_SIZE_LATEX

logger = logging.getLogger("procoo_qt")

# ------------------------------------------------------------------
#  Render settings
# ------------------------------------------------------------------

#: DPI the PNG is rasterised at. Higher than the 96 DPI logical baseline so the
#: glyphs stay crisp on HiDPI displays; the HTML ``width``/``height`` scale it
#: back down to logical pixels.
_RENDER_DPI = 192

#: Logical baseline DPI Qt uses for point-to-pixel conversion.
_BASE_DPI = 96

#: Transparent margin around the glyphs, in inches (inline / display).
_PAD_INLINE = 0.03
_PAD_DISPLAY = 0.06

#: Border width (points) of the emulated ``\boxed`` rectangle.
_BOX_LINEWIDTH = 0.8

#: Upper bound on the in-memory memo. The memo only avoids re-rasterising a
#: repeated expression within one process; it is never persisted.
_MEMO_MAX = 512


# ------------------------------------------------------------------
#  Value object
# ------------------------------------------------------------------


@dataclass(frozen=True)
class MathImage:
    """A rasterised math expression ready to inline into rich text.

    Attributes:
        uri: ``data:image/png;base64,...`` URI for the ``<img>`` source.
        width: Logical width in pixels.
        height: Logical height in pixels.
    """

    uri: str
    width: int
    height: int


# ------------------------------------------------------------------
#  Module state
# ------------------------------------------------------------------

_MEMO: OrderedDict[tuple[str, bool], MathImage | None] = OrderedDict()
_MEMO_LOCK = threading.Lock()
_RENDER_LOCK = threading.Lock()
_MATPLOTLIB_READY = False


# ------------------------------------------------------------------
#  Public API
# ------------------------------------------------------------------


def render_math_fragment(latex: str, *, display: bool) -> str:
    """Render a LaTeX expression to an inline HTML ``<img>`` tag.

    Args:
        latex: The LaTeX source without its ``$`` delimiters.
        display: Whether this is a display (block) expression. Only affects the
            transparent padding and the memo key; mathtext has no display style.

    Returns:
        An ``<img>`` fragment backed by a ``data:`` URI, or an empty string when
        the expression is empty or cannot be parsed.
    """
    image = _render_math_image(latex, display=display)
    if image is None:
        return ""
    return f'<img src="{image.uri}" width="{image.width}" height="{image.height}">'


# ------------------------------------------------------------------
#  Private: boxed emulation
# ------------------------------------------------------------------

_BOXED_CMD = r"\boxed"
_MAX_BOX_DEPTH = 16


def _strip_boxed(latex: str, _depth: int = 0) -> tuple[str, bool]:
    """Remove ``\\boxed{…}`` wrappers for mathtext.

    mathtext has no ``\\boxed`` command, so the wrapper is stripped before
    typesetting and re-created as a drawn rectangle. The box is drawn only when
    the wrapper encloses the whole expression (the common ``\\boxed{answer}``
    form); a box around only part of an expression is dropped rather than drawn
    in the wrong place.

    Args:
        latex: The LaTeX source without delimiters.
        _depth: Current recursion depth for nested wrappers (internal).

    Returns:
        A ``(stripped_latex, box_whole)`` pair: the expression with every
        ``\\boxed`` wrapper removed, and whether a rectangle should be drawn
        around the entire rendered result.
    """
    out: list[str] = []
    residue: list[str] = []
    i = 0
    found = False
    length = len(latex)
    while i < length:
        if latex.startswith(_BOXED_CMD, i) and i + len(_BOXED_CMD) < length:
            cursor = i + len(_BOXED_CMD)
            if latex[cursor] != "{":
                out.append(latex[i])
                residue.append(latex[i])
                i += 1
                continue
            cursor += 1
            depth = 1
            inner_start = cursor
            while cursor < length and depth:
                char = latex[cursor]
                if char == "\\" and cursor + 1 < length:
                    cursor += 2
                    continue
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        break
                cursor += 1
            out.append(
                _strip_boxed(latex[inner_start:cursor], _depth + 1)[0]
                if _depth < _MAX_BOX_DEPTH
                else latex[inner_start:cursor]
            )
            found = True
            i = cursor + 1
        else:
            out.append(latex[i])
            residue.append(latex[i])
            i += 1
    return "".join(out), found and not "".join(residue).strip()


# ------------------------------------------------------------------
#  Private: memo and rasterisation
# ------------------------------------------------------------------


def _render_math_image(latex: str, *, display: bool) -> MathImage | None:
    """Return a memoised :class:`MathImage` for an expression.

    Args:
        latex: The LaTeX source without delimiters.
        display: Whether this is a display expression.

    Returns:
        The rendered image, or ``None`` when rendering failed.
    """
    if not latex.strip():
        return None
    key = (latex, display)
    with _MEMO_LOCK:
        if key in _MEMO:
            _MEMO.move_to_end(key)
            return _MEMO[key]
    image = _build_math_image(latex, display=display)
    with _MEMO_LOCK:
        _MEMO[key] = image
        _MEMO.move_to_end(key)
        while len(_MEMO) > _MEMO_MAX:
            _MEMO.popitem(last=False)
    return image


def _build_math_image(latex: str, *, display: bool) -> MathImage | None:
    """Rasterise an expression and wrap it as a data-URI image.

    ``\\boxed{…}`` is emulated by stripping the wrapper for mathtext and drawing
    the rectangle afterwards (see :func:`_strip_boxed`).

    Args:
        latex: The LaTeX source without delimiters.
        display: Whether this is a display expression.

    Returns:
        The image, or ``None`` when matplotlib cannot parse the expression.
    """
    stripped, boxed = _strip_boxed(latex)
    png = _render_png(stripped, display=display, boxed=boxed)
    if png is None:
        return None
    width, height = _logical_size(_png_size(png))
    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    return MathImage(uri=uri, width=width, height=height)


def _render_png(latex: str, *, display: bool, boxed: bool) -> bytes | None:
    """Rasterise a LaTeX expression to transparent PNG bytes.

    matplotlib is imported lazily so application startup pays nothing when no
    math appears. Rendering is serialised because matplotlib is not thread-safe.

    Args:
        latex: The LaTeX source without delimiters and without ``\\boxed``.
        display: Whether this is a display expression.
        boxed: Whether to draw a rectangle around the rendered expression.

    Returns:
        PNG bytes, or ``None`` when the expression cannot be parsed.
    """
    global _MATPLOTLIB_READY
    with _RENDER_LOCK:
        try:
            if not _MATPLOTLIB_READY:
                import matplotlib

                matplotlib.use("Agg")
                matplotlib.rcParams["mathtext.fontset"] = "cm"
                _MATPLOTLIB_READY = True
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure

            figure = Figure()
            FigureCanvasAgg(figure)
            text = figure.text(
                0.0,
                0.0,
                f"${latex}$",
                fontsize=FONT_SIZE_LATEX,
                color=COLOR_MD_MATH,
            )
            if boxed:
                _draw_box(figure, text)
            buffer = io.BytesIO()
            figure.savefig(
                buffer,
                format="png",
                transparent=True,
                bbox_inches="tight",
                pad_inches=_PAD_DISPLAY if display else _PAD_INLINE,
                dpi=_RENDER_DPI,
            )
            return buffer.getvalue()
        except Exception:
            logger.warning("LaTeX render failed: %r", latex)
            return None


def _draw_box(figure: Any, text: Any) -> None:
    """Draw a rectangle around a rendered text artist.

    mathtext has no ``\\boxed``, so the border is added as a figure patch after
    the expression is typeset. ``bbox_inches="tight"`` includes the patch, so
    the saved image is cropped around the box.

    Args:
        figure: The matplotlib ``Figure``.
        text: The ``Text`` artist returned by ``figure.text``.
    """
    from matplotlib.patches import Rectangle

    bbox = text.get_window_extent(figure.canvas.get_renderer()).expanded(1.08, 1.5)
    (x0, y0), (x1, y1) = figure.transFigure.inverted().transform(
        [[bbox.x0, bbox.y0], [bbox.x1, bbox.y1]]
    )
    figure.add_artist(
        Rectangle(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            transform=figure.transFigure,
            fill=False,
            edgecolor=COLOR_MD_MATH,
            linewidth=_BOX_LINEWIDTH,
        )
    )


def _png_size(png: bytes) -> tuple[int, int]:
    """Read the pixel dimensions from a PNG header.

    Args:
        png: PNG bytes produced by :func:`_render_png`.

    Returns:
        The ``(width, height)`` pixel size, or ``(1, 1)`` for a truncated file.
        PNG stores both as big-endian uint32 immediately after the IHDR marker.
    """
    if len(png) < 24:
        return 1, 1
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


def _logical_size(pixel_size: tuple[int, int]) -> tuple[int, int]:
    """Convert raster pixel dimensions to logical pixels.

    Args:
        pixel_size: The ``(width, height)`` of the PNG at :data:`_RENDER_DPI`.

    Returns:
        The ``(width, height)`` in logical pixels at :data:`_BASE_DPI`.
    """
    width, height = pixel_size
    scale = _BASE_DPI / _RENDER_DPI
    return max(1, round(width * scale)), max(1, round(height * scale))
