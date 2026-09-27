"""Tool: read file content. Dispatch via ``mode``: text / pdf-text / docx / pptx /
xlsx / pdf-image / pdf-ocr / image. Visual modes select effort level via
``submode`` (thumbnail / cropping / full / ocr / test / test-resolution).
Optionally convert extracted content to .txt via ``convert=True``.
"""

import asyncio
import base64
import concurrent.futures
import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
import traceback

MAX_LINES = 500
MAX_CHARS = 15000

THUMBNAIL_SIZE = 500
THUMBNAIL_MAX_PER_IMAGE = 16
THUMBNAIL_LABEL_MARGIN = 10

MAX_DIM = 3000
OCR_SERVER = "http://localhost:3334/ocr"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _format_lines(
    lines: list[str],
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """Apply cat -n style line numbers and MAX_LINES / MAX_CHARS caps.

    Args:
        lines: Raw lines with trailing newlines (as from f.readlines() or
            document reader output).
        offset: 1-indexed line number to start reading from.
        limit: Maximum number of lines to return.

    Returns:
        Formatted string with right-aligned line numbers + tab + content.
    """
    total_file_lines = len(lines)

    start = (offset - 1) if offset is not None else 0
    end = (start + limit) if limit is not None else total_file_lines

    if start < 0:
        start = 0
    if end > total_file_lines:
        end = total_file_lines

    if start >= total_file_lines:
        return f"(offset {offset} exceeds file length of {total_file_lines} lines)"

    selected = lines[start:end]
    total_selected = len(selected)

    last_display_num = start + min(total_selected, MAX_LINES)
    line_width = max(len(str(last_display_num)), 1)

    output_lines: list[str] = []
    char_count = 0
    hit_line_limit = False
    hit_char_limit = False

    for i, line in enumerate(selected):
        line_num = start + i + 1
        prefix = f"{line_num:>{line_width}}\t"
        formatted = prefix + line
        output_lines.append(formatted)
        char_count += len(formatted)
        if i + 1 >= MAX_LINES:
            hit_line_limit = True
            break
        if char_count >= MAX_CHARS:
            hit_char_limit = True
            break

    result = ""

    if hit_line_limit or hit_char_limit:
        result += (
            f"(Result limited to first {i + 1} lines. "
            f"Selected portion has {total_selected} lines total.)\n"
        )

    result += "".join(output_lines)
    return result if result else "(empty)"


# ---------------------------------------------------------------------------
# Extract functions — return raw content (no line numbers, no caps)
# ---------------------------------------------------------------------------


def _text_extract(file_path: str) -> str:
    """Read raw text content from a file.

    Args:
        file_path: Absolute path to the file to read.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


async def _pdf_text_extract(file_path: str) -> str:
    """Extract raw text from PDF using PyMuPDF.

    Args:
        file_path: Absolute path to the PDF file.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"

    try:
        import pymupdf
    except ImportError:
        return "PyMuPDF is not installed. Install it with: pip install PyMuPDF"

    doc = pymupdf.open(str(file_path))
    try:
        parts: list[str] = []
        for page in doc:  # type: ignore[union-attr]
            page_text = page.get_text()  # type: ignore[union-attr]
            if page_text:
                parts.append(page_text)
        return "\n".join(parts)
    finally:
        doc.close()


async def _docx_extract(file_path: str) -> str:
    """Extract raw text from DOCX using python-docx.

    Args:
        file_path: Absolute path to the DOCX file.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"

    try:
        from docx import Document
    except ImportError:
        return "python-docx is not installed. Install it with: pip install python-docx"

    doc = Document(file_path)
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text:
            parts.append(para.text)
    return "\n".join(parts)


async def _pptx_extract(file_path: str) -> str:
    """Extract raw text from PPTX/PPT using python-pptx.

    Args:
        file_path: Absolute path to the PPTX/PPT file.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"

    try:
        from pptx import Presentation
    except ImportError:
        return "python-pptx is not installed. Install it with: pip install python-pptx"

    prs = Presentation(file_path)
    parts: list[str] = []
    for i, slide in enumerate(prs.slides):
        slide_lines: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                slide_lines.append(shape.text)
        if slide_lines:
            parts.append(f"# Slide {i + 1}")
            parts.extend(slide_lines)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
#  mode: text
# ---------------------------------------------------------------------------


async def _text(
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """Read text content from a file with cat -n style line numbers.

    Args:
        file_path: Absolute path to the file to read.
        offset: 1-indexed line number to start reading from. Omit to read from
            the beginning.
        limit: Maximum number of lines to return. Omit to read to end of file
            (subject to MAX_LINES / MAX_CHARS caps).
    """
    content = _text_extract(file_path)
    if content.startswith("File not found:") or content.startswith("Not a file:"):
        return content
    raw_lines = [line + "\n" for line in content.split("\n")]
    return _format_lines(raw_lines, offset, limit)


# ---------------------------------------------------------------------------
#  mode: pdf-text — PyMuPDF
# ---------------------------------------------------------------------------


async def _pdf_text(
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """Extract text from PDF using PyMuPDF.

    Args:
        file_path: Absolute path to the PDF file.
        offset: 1-indexed line number to start reading from.
        limit: Maximum number of lines to return (subject to caps).
    """
    content = await _pdf_text_extract(file_path)
    if content.startswith(("File not found:", "Not a file:", "PyMuPDF")):
        return content
    raw_lines = [line + "\n" for line in content.split("\n")]
    return _format_lines(raw_lines, offset, limit)


# ---------------------------------------------------------------------------
#  mode: docx — python-docx
# ---------------------------------------------------------------------------


async def _docx(
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """Extract text from DOCX using python-docx.

    Args:
        file_path: Absolute path to the DOCX file.
        offset: 1-indexed line number to start reading from.
        limit: Maximum number of lines to return (subject to caps).
    """
    content = await _docx_extract(file_path)
    if content.startswith(("File not found:", "Not a file:", "python-docx")):
        return content
    raw_lines = [line + "\n" for line in content.split("\n")]
    return _format_lines(raw_lines, offset, limit)


# ---------------------------------------------------------------------------
#  mode: pptx — python-pptx
# ---------------------------------------------------------------------------


async def _pptx(
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """Extract text from PPTX/PPT using python-pptx.

    Args:
        file_path: Absolute path to the PPTX/PPT file.
        offset: 1-indexed line number to start reading from.
        limit: Maximum number of lines to return (subject to caps).
    """
    content = await _pptx_extract(file_path)
    if content.startswith(("File not found:", "Not a file:", "python-pptx")):
        return content
    raw_lines = [line + "\n" for line in content.split("\n")]
    return _format_lines(raw_lines, offset, limit)


# ---------------------------------------------------------------------------
#  Page parsing helper
# ---------------------------------------------------------------------------


def _parse_pages(pages_str: str) -> list[int]:
    """Parse a page selection string into a list of 1-indexed page numbers.

    Supports comma-separated single pages and closed ranges.
    Example: "1", "2-5", "1,3,5-7".

    Args:
        pages_str: Page selection string.

    Returns:
        List of 1-indexed page numbers, sorted and deduplicated.

    Raises:
        ValueError: If the string is empty or contains invalid syntax.
    """
    if not pages_str.strip():
        raise ValueError("Pages string must not be empty")
    result: list[int] = []
    for token in pages_str.split(","):
        token = token.strip()
        if "-" in token:
            parts = token.split("-", 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise ValueError(f"Invalid page range: {token!r}")
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            if start > end:
                raise ValueError(f"Invalid page range (start > end): {token!r}")
            result.extend(range(start, end + 1))
        else:
            result.append(int(token))
    return sorted(set(result))


# ---------------------------------------------------------------------------
#  XLSX helpers
# ---------------------------------------------------------------------------


def _sheet_to_csv(ws) -> str:
    """Convert an openpyxl worksheet to CSV text, stripping trailing empty rows.

    Args:
        ws: An openpyxl worksheet object.

    Returns:
        CSV-formatted string.
    """
    buf = StringIO()
    writer = csv.writer(buf)
    pending_empties: list[tuple] = []
    for row in ws.iter_rows(values_only=True):
        if any(cell is not None and cell != "" for cell in row):
            for empty_row in pending_empties:
                writer.writerow(empty_row)
            pending_empties.clear()
            writer.writerow(row)
        else:
            pending_empties.append(tuple(row))
    return buf.getvalue()


async def _xlsx_extract(
    file_path: str,
    sheet: str | None = None,
) -> str:
    """Extract CSV text from an XLSX sheet.

    Args:
        file_path: Absolute path to the XLSX file.
        sheet: Sheet name to extract.  Defaults to the first sheet.

    Returns:
        Raw CSV text, or an error string on failure.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"

    try:
        import openpyxl
    except ImportError:
        return "openpyxl is not installed. Install it with: pip install openpyxl"

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)

    try:
        if sheet:
            if sheet not in wb.sheetnames:
                wb.close()
                return f"Sheet {sheet!r} not found. Available sheets: {', '.join(wb.sheetnames)}"
            ws = wb[sheet]
        else:
            ws = wb[wb.sheetnames[0]]

        return _sheet_to_csv(ws)
    finally:
        wb.close()


# ---------------------------------------------------------------------------
#  mode: xlsx — openpyxl
# ---------------------------------------------------------------------------


async def _xlsx(
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
    sheet: str | None = None,
) -> str:
    """Read an XLSX file, returning the selected sheet as CSV text.

    When the workbook contains multiple sheets, a header line is prepended
    listing all available sheets and indicating which one is shown.

    Args:
        file_path: Absolute path to the XLSX file.
        offset: 1-indexed line number to start reading from.
        limit: Maximum number of lines to return (subject to caps).
        sheet: Sheet name to read.  Defaults to the first sheet.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"

    try:
        import openpyxl
    except ImportError:
        return "openpyxl is not installed. Install it with: pip install openpyxl"

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)

    try:
        target_sheet: str
        if sheet:
            if sheet not in wb.sheetnames:
                wb.close()
                return f"Sheet {sheet!r} not found. Available sheets: {', '.join(wb.sheetnames)}"
            target_sheet = sheet
        else:
            target_sheet = wb.sheetnames[0]

        content = _sheet_to_csv(wb[target_sheet])

        raw_lines = [line + "\n" for line in content.split("\n")]
        formatted = _format_lines(raw_lines, offset, limit)

        if len(wb.sheetnames) > 1:
            sheet_list = ", ".join(wb.sheetnames)
            header = (
                f"{len(wb.sheetnames)} sheets found in excel: {sheet_list} "
                f"— now returning result of {target_sheet}"
            )
            return f"{header}\n{formatted}"

        return formatted
    finally:
        wb.close()


# ---------------------------------------------------------------------------
#  Vision helpers — clamp, bbox, encode
# ---------------------------------------------------------------------------


def _clamp_size(width: int, height: int) -> tuple[int, int]:
    """Proportionally downscale dimensions to fit within MAX_DIM x MAX_DIM.

    Args:
        width: Original pixel width.
        height: Original pixel height.

    Returns:
        Tuple of (width, height), downscaled if either exceeds MAX_DIM.
    """
    scale = min(1.0, MAX_DIM / width, MAX_DIM / height)
    if scale < 1.0:
        return round(width * scale), round(height * scale)
    return width, height


def _clamp_image(img):
    """Downscale a PIL image to fit within MAX_DIM x MAX_DIM (in place-safe).

    Args:
        img: A PIL Image.

    Returns:
        The (possibly resized) PIL Image.
    """
    from PIL import Image

    width, height = img.size
    new_w, new_h = _clamp_size(width, height)
    if (new_w, new_h) != (width, height):
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return img


def _parse_bbox(bbox) -> tuple[float, float, float, float]:
    """Validate a normalized bounding box and return its four fractions.

    Args:
        bbox: A list/tuple of 4 numbers ``[x0, y0, x1, y1]``.

    Returns:
        Tuple of four floats.

    Raises:
        ValueError: If the bbox is missing, the wrong length, or non-numeric.
    """
    if bbox is None:
        raise ValueError("bbox is required for the cropping submode")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("bbox must be [x0, y0, x1, y1] with 4 numeric values")
    try:
        x0, y0, x1, y1 = bbox
        return (float(x0), float(y0), float(x1), float(y1))
    except (TypeError, ValueError) as e:
        raise ValueError("bbox must contain 4 numeric values") from e


def _crop_rect(bbox, width: int, height: int) -> tuple[int, int, int, int]:
    """Convert a normalized bbox to a clipped pixel rectangle.

    Args:
        bbox: Normalized ``[x0, y0, x1, y1]`` fractions (0-1).
        width: Pixel width of the source image.
        height: Pixel height of the source image.

    Returns:
        Tuple ``(left, top, right, bottom)`` in pixel coordinates.

    Raises:
        ValueError: If the bbox is invalid or empty.
    """
    x0, y0, x1, y1 = _parse_bbox(bbox)
    x0 = max(0.0, min(1.0, x0))
    y0 = max(0.0, min(1.0, y0))
    x1 = max(0.0, min(1.0, x1))
    y1 = max(0.0, min(1.0, y1))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bbox must satisfy x1 > x0 and y1 > y0")
    return (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))


def _img_to_b64(img) -> str:
    """Encode a PIL image as a base64 WebP string.

    Args:
        img: A PIL Image.

    Returns:
        Base64-encoded WebP string.
    """
    img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _pix_to_png(pix, bbox=None) -> tuple[str, int, int]:
    """Render a pymupdf pixmap to a base64 WebP, optionally cropping.

    The result is clamped to MAX_DIM x MAX_DIM.

    Args:
        pix: A pymupdf pixmap.
        bbox: Optional normalized ``[x0, y0, x1, y1]`` crop region.

    Returns:
        Tuple of ``(base64_webp, width, height)``.

    Raises:
        ValueError: If the bbox is invalid.
    """
    from PIL import Image

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    if bbox is not None:
        rect = _crop_rect(bbox, pix.width, pix.height)
        img = img.crop(rect)
    img = _clamp_image(img)
    return _img_to_b64(img), img.size[0], img.size[1]


def _resize_by_dpi(img, dpi: int | None):
    """Resample a PIL image by a dpi/72 scale factor (no-op when dpi is None).

    Args:
        img: A PIL Image.
        dpi: Optional resolution; scale factor is ``dpi / 72``.

    Returns:
        The (possibly resized) PIL Image.
    """
    if not dpi:
        return img
    scale = dpi / 72.0
    if scale <= 0 or abs(scale - 1.0) < 1e-9:
        return img
    from PIL import Image

    w, h = img.size
    return img.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))),
        Image.Resampling.LANCZOS,
    )


# ---------------------------------------------------------------------------
#  mode: image — read image file via PIL (submode dispatch)
# ---------------------------------------------------------------------------


async def _image(
    file_path: str,
    submode: str | None = None,
    dpi: int | None = None,
    bbox=None,
    thumb_size: int = 500,
    target: str | None = None,
) -> str:
    """Read an image file, dispatching on ``submode`` (ocr / thumbnail /
    cropping / full / test / test-resolution).

    Args:
        file_path: Absolute path to the image file.
        submode: Effort level. Defaults to "full".
        dpi: Optional resample scale (``dpi / 72``) for full/cropping.
        bbox: Normalized ``[x0, y0, x1, y1]`` crop region (cropping only).
        thumb_size: Longest-side size in px for the thumbnail submode.
        target: Real submode to report size for (test-resolution only).
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"

    suff = path.suffix.lower()
    if suff not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        return f"Unsupported image format: {suff}. Supported: .png, .jpg, .jpeg, .gif, .webp, .bmp"

    try:
        from PIL import Image
    except ImportError:
        return "Pillow is not installed. Install it with: pip install Pillow"

    sub = (submode or "full").lower()

    if sub == "test":
        return await _probe_ocr()

    try:
        img = Image.open(str(path))
        img.load()
        width, height = img.size
        file_size = path.stat().st_size
    except Exception as e:
        return f"Failed to read image: {e}"

    if sub == "ocr":
        return await _image_ocr(img)

    if sub == "test-resolution":
        return _image_test_resolution(width, height, target, dpi, bbox, thumb_size)

    if sub == "thumbnail":
        out = _resize_to_thumb(img, thumb_size)
        w, h = out.size
        return _media_output_image(f"{path.name} (thumbnail {w}x{h})", out)

    if sub == "cropping":
        try:
            rect = _crop_rect(bbox, width, height)
        except ValueError as e:
            return f"Invalid bbox: {e}"
        out = img.crop(rect)
        out = _resize_by_dpi(out, dpi)
        out = _clamp_image(out)
        w, h = out.size
        return _media_output_image(f"{path.name} (crop {w}x{h})", out)

    if sub == "full":
        out = _resize_by_dpi(img, dpi)
        out = _clamp_image(out)
        w, h = out.size
        size_str = _format_file_size(file_size)
        return _media_output_image(f"{path.name} ({w}x{h}, {size_str})", out)

    return (
        f"Unknown submode: {sub!r}. Valid: full, ocr, thumbnail, cropping, test, test-resolution."
    )


def _resize_to_thumb(img, thumb_size: int):
    """Resize an image so its longest side equals ``thumb_size``.

    Args:
        img: A PIL Image.
        thumb_size: Longest-side target in px.

    Returns:
        The resized PIL Image.
    """
    from PIL import Image

    w, h = img.size
    longest = max(w, h)
    if longest <= thumb_size:
        return img
    scale = thumb_size / longest
    return img.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))),
        Image.Resampling.LANCZOS,
    )


def _media_output_image(desc: str, img) -> str:
    """Build the ``_media`` marker output for a single PIL image.

    Args:
        desc: Human-readable description.
        img: A PIL Image.

    Returns:
        JSON string with ``_media`` marker.
    """
    img_b64 = _img_to_b64(img)
    return _format_media_output(
        text="Image read — sent as user message",
        media=[{"desc": desc, "data": img_b64}],
    )


async def _image_ocr(img) -> str:
    """Send a PIL image to the OCR server and return the markdown.

    Args:
        img: A PIL Image.

    Returns:
        OCR markdown text, or an error string.
    """
    img_b64 = _img_to_b64(img)
    markdown = await _ocr_images([img_b64])
    if not markdown:
        return "(empty)"
    return markdown


def _image_test_resolution(
    width: int,
    height: int,
    target: str | None,
    dpi: int | None,
    bbox,
    thumb_size: int,
) -> str:
    """Report the output pixel size for an image submode without producing it.

    Args:
        width: Original image width in px.
        height: Original image height in px.
        target: Submode to report size for (full / cropping / thumbnail).
        dpi: Resample scale for full.
        bbox: Crop region for cropping.
        thumb_size: Thumbnail longest side.

    Returns:
        JSON string of ``{"results": [...]}`` or an error string.
    """
    target = (target or "full").lower()

    if target == "full":
        w, h = width, height
        if dpi:
            scale = dpi / 72.0
            w, h = round(w * scale), round(h * scale)
    elif target == "cropping":
        try:
            rect = _crop_rect(bbox, width, height)
        except ValueError as e:
            return f"Invalid bbox: {e}"
        w, h = rect[2] - rect[0], rect[3] - rect[1]
    elif target == "thumbnail":
        scale = min(1.0, thumb_size / max(width, height))
        w, h = round(width * scale), round(height * scale)
        return json.dumps(
            {
                "results": [
                    {
                        "width": w,
                        "height": h,
                        "clamped": False,
                        "final_width": w,
                        "final_height": h,
                    }
                ]
            }
        )
    else:
        return f"Unknown target: {target!r}. Valid: full, cropping, thumbnail."

    cw, ch = _clamp_size(w, h)
    return json.dumps(
        {
            "results": [
                {
                    "width": w,
                    "height": h,
                    "clamped": (cw, ch) != (w, h),
                    "final_width": cw,
                    "final_height": ch,
                }
            ]
        }
    )


# ---------------------------------------------------------------------------
#  mode: pdf-image — render PDF pages as images (submode dispatch)
# ---------------------------------------------------------------------------


async def _pdf_image(
    file_path: str,
    pages: str | None = None,
    dpi: int | None = None,
    submode: str | None = None,
    bbox=None,
    target: str | None = None,
) -> str:
    """Render PDF pages to WebP images and return via the ``_media`` marker.

    Effort selected by ``submode``: ``full`` (default), ``thumbnail``,
    ``cropping``, or ``test-resolution``.

    Args:
        file_path: Absolute path to the PDF file.
        pages: Page selection string (e.g. "1", "2-5", "1,3,5-7").
            Defaults to "1" for full/cropping; all pages for thumbnail.
        dpi: Image resolution in dots per inch.  Defaults to 150.
        submode: Effort level.  Defaults to "full".
        bbox: Normalized ``[x0, y0, x1, y1]`` crop region (cropping only).
        target: Real submode to report size for (test-resolution only).
    """
    dpi = dpi or 150
    sub = (submode or "full").lower()

    try:
        import pymupdf
    except ImportError:
        return "PyMuPDF is not installed. Install it with: pip install PyMuPDF"

    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"

    doc = pymupdf.open(str(path))
    total_pages = doc.page_count

    try:
        if sub == "test-resolution":
            return _pdf_image_test_resolution(doc, pages, dpi, bbox, target)

        try:
            if sub == "thumbnail":
                page_list = _parse_pages(pages) if pages else list(range(1, total_pages + 1))
            else:
                page_list = _parse_pages(pages or "1")
        except ValueError as e:
            return f"Invalid pages string: {e}"

        for p in page_list:
            if p < 1 or p > total_pages:
                return f"Page {p} out of range. PDF has {total_pages} pages."

        if sub == "thumbnail":
            return await _pdf_image_thumbnail(str(path), page_list, path.name)
        if sub == "cropping":
            return await _pdf_image_cropping(doc, page_list, dpi, bbox, path.name, total_pages)
        if sub == "full":
            return await _pdf_image_full(doc, page_list, dpi, path.name, total_pages)
        return f"Unknown submode: {sub!r}. Valid: full, thumbnail, cropping, test-resolution."
    finally:
        if doc:
            doc.close()


async def _pdf_image_thumbnail(
    pdf_path: str,
    page_list: list[int],
    filename: str,
) -> str:
    """Render pages as thumbnail grids (sub-mode of pdf-image).

    Args:
        pdf_path: Absolute path to the PDF file (as string for worker).
        page_list: List of 1-indexed page numbers to render.
        filename: Display name for the description.
    """
    tasks = [(pdf_path, p) for p in page_list]

    loop = asyncio.get_running_loop()
    with concurrent.futures.ProcessPoolExecutor() as pool:
        futures = [loop.run_in_executor(pool, _render_thumbnail_worker, task) for task in tasks]
        thumb_pngs: list[bytes] = list(await asyncio.gather(*futures))

    combined_pngs: list[bytes] = []
    batch_start = 0

    while batch_start < len(thumb_pngs):
        batch = thumb_pngs[batch_start : batch_start + THUMBNAIL_MAX_PER_IMAGE]
        batch_size = len(batch)
        cols, rows = _get_thumbnail_grid_layout(batch_size)
        combined_pngs.append(_combine_thumbnails(batch, cols, rows))
        batch_start += THUMBNAIL_MAX_PER_IMAGE

    media: list[dict] = []
    for idx, png_data in enumerate(combined_pngs):
        img_b64 = base64.b64encode(png_data).decode("utf-8")
        grid_cols, grid_rows = _get_thumbnail_grid_layout(
            min(len(thumb_pngs) - idx * THUMBNAIL_MAX_PER_IMAGE, THUMBNAIL_MAX_PER_IMAGE)
        )
        desc = (
            f"{filename} (thumbnails "
            f"#{idx * THUMBNAIL_MAX_PER_IMAGE + 1}-"
            f"{min((idx + 1) * THUMBNAIL_MAX_PER_IMAGE, len(page_list))}, "
            f"{grid_cols}x{grid_rows} grid)"
        )
        media.append({"desc": desc, "data": img_b64})

    total = len(page_list)
    if total == 1:
        text = "1 page rendered as thumbnail — sent as user message"
    else:
        text = f"{total} pages rendered as thumbnails — sent as user message"
    return _format_media_output(text=text, media=media)


async def _pdf_image_full(
    doc,
    page_list: list[int],
    dpi: int,
    filename: str,
    total_pages: int,
) -> str:
    """Render pages as full-resolution images (default pdf-image behavior).

    Args:
        doc: pymupdf document (open).
        page_list: List of 1-indexed page numbers to render.
        dpi: Image resolution in dots per inch.
        filename: Display name for the description.
        total_pages: Total page count of the PDF.
    """
    media: list[dict] = []
    for p in page_list:
        pix = doc[p - 1].get_pixmap(dpi=dpi)  # type: ignore[union-attr]
        img_b64, width, height = _pix_to_png(pix)
        desc = f"{filename} (Page {p}/{total_pages}, {width}x{height})"
        media.append({"desc": desc, "data": img_b64})

    if len(page_list) == 1:
        text = "1 page read — sent as user message"
    else:
        text = f"{len(page_list)} pages read — sent as user message"
    return _format_media_output(text=text, media=media)


async def _pdf_image_cropping(
    doc,
    page_list: list[int],
    dpi: int,
    bbox,
    filename: str,
    total_pages: int,
) -> str:
    """Render pages at ``dpi``, crop each by ``bbox``, and return the slices.

    Args:
        doc: pymupdf document (open).
        page_list: List of 1-indexed page numbers to render.
        dpi: Image resolution in dots per inch.
        bbox: Normalized ``[x0, y0, x1, y1]`` crop region.
        filename: Display name for the description.
        total_pages: Total page count of the PDF.
    """
    media: list[dict] = []
    for p in page_list:
        pix = doc[p - 1].get_pixmap(dpi=dpi)  # type: ignore[union-attr]
        try:
            img_b64, width, height = _pix_to_png(pix, bbox)
        except ValueError as e:
            return f"Invalid bbox: {e}"
        desc = f"{filename} (Page {p}/{total_pages}, crop {width}x{height})"
        media.append({"desc": desc, "data": img_b64})

    if len(page_list) == 1:
        text = "1 region cropped — sent as user message"
    else:
        text = f"{len(page_list)} regions cropped — sent as user message"
    return _format_media_output(text=text, media=media)


def _pdf_image_test_resolution(
    doc,
    pages: str | None,
    dpi: int,
    bbox,
    target: str | None,
) -> str:
    """Report the output pixel size for a pdf-image submode without rendering.

    Args:
        doc: pymupdf document (open).
        pages: Page selection string.
        dpi: Render resolution in dots per inch.
        bbox: Crop region (cropping target only).
        target: Submode to report size for (full / cropping / thumbnail).

    Returns:
        JSON string of ``{"results": [...]}`` or an error string.
    """
    target = (target or "full").lower()

    if target == "thumbnail":
        try:
            thumb_pages = _parse_pages(pages) if pages else list(range(1, doc.page_count + 1))
        except ValueError as e:
            return f"Invalid pages string: {e}"
        cols, rows = _get_thumbnail_grid_layout(min(len(thumb_pages), THUMBNAIL_MAX_PER_IMAGE))
        gw, gh = cols * THUMBNAIL_SIZE, rows * THUMBNAIL_SIZE
        return json.dumps(
            {
                "results": [
                    {
                        "page": None,
                        "width": gw,
                        "height": gh,
                        "clamped": False,
                        "final_width": gw,
                        "final_height": gh,
                    }
                ]
            }
        )

    if target not in ("full", "cropping"):
        return f"Unknown target: {target!r}. Valid: full, cropping, thumbnail."

    try:
        page_list = _parse_pages(pages or "1")
    except ValueError as e:
        return f"Invalid pages string: {e}"

    total_pages = doc.page_count
    for p in page_list:
        if p < 1 or p > total_pages:
            return f"Page {p} out of range. PDF has {total_pages} pages."

    results: list[dict] = []
    for p in page_list:
        rect = doc[p - 1].rect  # type: ignore[union-attr]
        pw = rect.width * dpi / 72.0
        ph = rect.height * dpi / 72.0
        if target == "cropping":
            try:
                x0, y0, x1, y1 = _parse_bbox(bbox)
            except ValueError as e:
                return f"Invalid bbox: {e}"
            x0 = max(0.0, min(1.0, x0))
            y0 = max(0.0, min(1.0, y0))
            x1 = max(0.0, min(1.0, x1))
            y1 = max(0.0, min(1.0, y1))
            w = round((x1 - x0) * pw)
            h = round((y1 - y0) * ph)
        else:
            w, h = round(pw), round(ph)
        cw, ch = _clamp_size(w, h)
        results.append(
            {
                "page": p,
                "width": w,
                "height": h,
                "clamped": (cw, ch) != (w, h),
                "final_width": cw,
                "final_height": ch,
            }
        )
    return json.dumps({"results": results})


# ---------------------------------------------------------------------------
#  mode: pdf-ocr — render PDF pages and OCR via server (submode dispatch)
# ---------------------------------------------------------------------------


async def _pdf_ocr(
    file_path: str,
    pages: str | None = None,
    dpi: int | None = None,
    submode: str | None = None,
    bbox=None,
) -> str:
    """OCR PDF pages via the OCR server, dispatching on ``submode``.

    Effort selected by ``submode``: ``full`` (default), ``cropping``, or
    ``test``. Renders pages to images and POSTs them to the OCR server.

    Args:
        file_path: Absolute path to the PDF file.
        pages: Page selection string (e.g. "1", "2-5", "1,3,5-7").
            Defaults to "1".
        dpi: Render resolution in dots per inch.  Defaults to 150.
        submode: Effort level.  Defaults to "full".
        bbox: Normalized ``[x0, y0, x1, y1]`` crop region (cropping only).
    """
    dpi = dpi or 150
    sub = (submode or "full").lower()

    if sub == "test":
        return await _probe_ocr()

    if sub not in ("full", "cropping"):
        return f"Unknown submode: {sub!r}. Valid: full, cropping, test."

    try:
        import pymupdf
    except ImportError:
        return "PyMuPDF is not installed. Install it with: pip install PyMuPDF"

    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"

    doc = pymupdf.open(str(path))
    total_pages = doc.page_count

    try:
        try:
            page_list = _parse_pages(pages or "1")
        except ValueError as e:
            return f"Invalid pages string: {e}"

        for p in page_list:
            if p < 1 or p > total_pages:
                return f"Page {p} out of range. PDF has {total_pages} pages."

        images_b64: list[str] = []
        for p in page_list:
            pix = doc[p - 1].get_pixmap(dpi=dpi)  # type: ignore[union-attr]
            try:
                img_b64, _, _ = _pix_to_png(pix, bbox if sub == "cropping" else None)
            except ValueError as e:
                return f"Invalid bbox: {e}"
            images_b64.append(img_b64)

        markdown = await _ocr_images(images_b64)
        if markdown.startswith(("OCR server", "aiohttp")):
            return markdown
        if not markdown:
            return "(empty)"
        if len(page_list) == 1:
            header = f"(Page {page_list[0]} of {total_pages})"
        else:
            header = f"(Pages {', '.join(str(p) for p in page_list)} of {total_pages})"
        return f"{header}\n{markdown}"
    finally:
        if doc:
            doc.close()


# ---------------------------------------------------------------------------
#  OCR server client
# ---------------------------------------------------------------------------


async def _ocr_images(images_b64: list[str]) -> str:
    """POST base64 images to the OCR server and return markdown.

    Args:
        images_b64: List of base64-encoded WebP strings.

    Returns:
        Markdown text from the server, or an error string.
    """
    try:
        import aiohttp
    except ImportError:
        return "aiohttp is not installed. Install it with: pip install aiohttp"

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                OCR_SERVER,
                json={"images": images_b64},
                timeout=aiohttp.ClientTimeout(total=300 * max(1, len(images_b64))),
            ) as resp,
        ):
            data = await resp.json()
            if resp.status == 200:
                return data.get("markdown", "")
            return data.get("error", f"OCR server error {resp.status}")
    except Exception as e:
        return f"OCR server unavailable: {e}"


async def _probe_ocr() -> str:
    """Check whether the OCR server is reachable.

    Returns:
        JSON string ``{"available": bool, ...}``.
    """
    import time

    try:
        import aiohttp
    except ImportError:
        return json.dumps({"available": False, "error": "aiohttp is not installed"})

    start = time.perf_counter()
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                OCR_SERVER,
                json={"images": []},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp,
        ):
            latency_ms = round((time.perf_counter() - start) * 1000)
            return json.dumps({"available": True, "status": resp.status, "latency_ms": latency_ms})
    except Exception as e:
        return json.dumps({"available": False, "error": str(e)})


# ---------------------------------------------------------------------------
#  Media output helper
# ---------------------------------------------------------------------------


def _format_media_output(text: str, media: list[dict]) -> str:
    """Build the JSON payload used to signal image results to the main process.

    Args:
        text: Human-readable summary for the tool result message.
        media: List of ``{"desc": str, "data": base64_str}`` entries.

    Returns:
        JSON string with ``_media`` marker.
    """
    return json.dumps({"_media": True, "text": text, "media": media})


def _format_file_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable string.

    Args:
        num_bytes: Number of bytes.

    Returns:
        Formatted string like ``"234KB"`` or ``"1.2MB"``.
    """
    if num_bytes < 1024:
        return f"{num_bytes}B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.0f}KB"
    return f"{num_bytes / (1024 * 1024):.1f}MB"


# ---------------------------------------------------------------------------
#  Thumbnail helpers (sub-mode of pdf-image)
# ---------------------------------------------------------------------------


def _get_thumbnail_grid_layout(num_pages: int) -> tuple[int, int]:
    """Determine grid columns and rows for given number of pages.

    Args:
        num_pages: Number of pages (1-16).

    Returns:
        Tuple of (columns, rows).
    """
    if num_pages == 1:
        return (1, 1)
    if num_pages == 2:
        return (2, 1)
    if num_pages <= 4:
        return (2, 2)
    if num_pages <= 6:
        return (3, 2)
    if num_pages <= 8:
        return (4, 2)
    if num_pages == 9:
        return (3, 3)
    if num_pages <= 12:
        return (3, 4)
    return (4, 4)


def _create_thumbnail_page(pix, page_num: int) -> bytes:
    """Render a single PDF page pixmap as a 500x500 thumbnail WebP.

    The page image is scaled so its longer side is THUMBNAIL_SIZE px,
    keeping the original aspect ratio, then pasted centered onto a white
    500x500 square.  The actual PDF page number is drawn at the top-left.

    Args:
        pix: pymupdf pixmap (rendered page).
        page_num: Actual page number to label (1-indexed from PDF).

    Returns:
        WebP bytes of the 500x500 thumbnail.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    w, h = img.size
    if w >= h:
        new_w = THUMBNAIL_SIZE
        new_h = round(h * THUMBNAIL_SIZE / w)
    else:
        new_h = THUMBNAIL_SIZE
        new_w = round(w * THUMBNAIL_SIZE / h)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (THUMBNAIL_SIZE, THUMBNAIL_SIZE), "white")

    paste_x = (THUMBNAIL_SIZE - new_w) // 2
    paste_y = (THUMBNAIL_SIZE - new_h) // 2
    canvas.paste(img, (paste_x, paste_y))

    font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (THUMBNAIL_LABEL_MARGIN, THUMBNAIL_LABEL_MARGIN),
        str(page_num),
        fill="black",
        font=font,
    )

    buf = BytesIO()
    canvas.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


def _render_thumbnail_worker(args: tuple[str, int]) -> bytes:
    """Module-level worker to render a single PDF page thumbnail.

    Opens its own pymupdf document (required for ProcessPoolExecutor
    compatibility).

    Args:
        args: Tuple of (pdf_path, page_num).

    Returns:
        WebP bytes of the 500x500 thumbnail.
    """
    import pymupdf

    pdf_path, page_num = args
    doc = pymupdf.open(pdf_path)
    try:
        pix = doc[page_num - 1].get_pixmap(dpi=150)
        return _create_thumbnail_page(pix, page_num)
    finally:
        doc.close()


def _combine_thumbnails(
    thumb_pngs: list[bytes],
    cols: int,
    rows: int,
) -> bytes:
    """Assemble thumbnail WebPs into a single grid image.

    Args:
        thumb_pngs: List of 500x500 thumbnail WebP bytes (in page order).
        cols: Number of columns in the grid.
        rows: Number of rows in the grid.

    Returns:
        WebP bytes of the combined grid image.
    """
    from PIL import Image

    grid_w = cols * THUMBNAIL_SIZE
    grid_h = rows * THUMBNAIL_SIZE
    combined = Image.new("RGB", (grid_w, grid_h), "white")

    for idx, png_data in enumerate(thumb_pngs):
        thumb = Image.open(BytesIO(png_data))
        col = idx % cols
        row = idx // cols
        combined.paste(thumb, (col * THUMBNAIL_SIZE, row * THUMBNAIL_SIZE))

    buf = BytesIO()
    combined.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
#  Dispatch
# ---------------------------------------------------------------------------


async def run(
    mode: str = "text",
    file_path: str = "",
    offset: int | None = None,
    limit: int | None = None,
    pages: str | None = None,
    convert: bool = False,
    sheet: str | None = None,
    output_dir: str | None = None,
    dpi: int | None = None,
    submode: str | None = None,
    bbox: list | None = None,
    thumb_size: int = 500,
    target: str | None = None,
) -> str:
    """Read file contents, PDFs, and images, dispatching on ``mode``.

    Text modes (text / pdf-text / docx / pptx / xlsx) return formatted text
    with cat -n line numbers. Visual modes (pdf-image / pdf-ocr / image)
    select their effort level via ``submode``: pdf-image uses full/thumbnail/
    cropping/test-resolution; pdf-ocr uses full/cropping/test; image uses
    full/ocr/thumbnail/cropping/test/test-resolution. Use ``convert=true`` to
    persist extracted text to ``{stem}.txt``.

    Args:
        mode: Operation mode — "text", "pdf-text", "docx", "pptx", "xlsx",
            "pdf-image", "pdf-ocr", or "image". Defaults to "text".
        file_path: Absolute path to the file to read.
        offset: (text modes) 1-indexed line number to start reading from.
        limit: (text modes) Maximum number of lines to return.
        pages: (pdf-image / pdf-ocr) Page selection string
            (e.g. "1", "2-5", "1,3,5-7"). Defaults to "1" (all pages for
            thumbnail submode).
        convert: When True, extract and write full content to ``{stem}.txt``
            instead of returning formatted output.
        sheet: (xlsx) Sheet name to read. Defaults to the first sheet.
        output_dir: (convert) Directory to write the converted .txt file to.
            Defaults to the same directory as the input file.
        dpi: Render/resample resolution. Defaults to 150 for PDF modes; for
            image mode it is an optional ``dpi / 72`` resample scale.
        submode: Effort level for visual modes. Defaults per mode: pdf-image=
            "full", pdf-ocr="full", image="full".
        bbox: Normalized ``[x0, y0, x1, y1]`` crop region (cropping only).
        thumb_size: (image thumbnail) Longest side in px. Defaults to 500.
        target: (test-resolution) Real submode to report size for.
    """
    try:
        if convert:
            return await _convert_and_write(mode, file_path, pages, sheet, output_dir, dpi)
        return await _read(
            mode, file_path, offset, limit, pages, sheet, dpi, submode, bbox, thumb_size, target
        )
    except Exception:
        return json.dumps({"error": traceback.format_exc()})


async def _convert_and_write(
    mode: str,
    file_path: str,
    pages: str | None,
    sheet: str | None,
    output_dir: str | None,
    dpi: int | None = None,
) -> str:
    """Extract full content and write to disk.  Used when convert=True."""
    if mode == "text":
        content = _text_extract(file_path)
    elif mode == "pdf-text":
        content = await _pdf_text_extract(file_path)
    elif mode == "docx":
        content = await _docx_extract(file_path)
    elif mode == "pptx":
        content = await _pptx_extract(file_path)
    elif mode == "xlsx":
        content = await _xlsx_extract(file_path, sheet)
    elif mode == "pdf-ocr":
        content = await _pdf_ocr_convert(file_path, dpi)
    elif mode in ("image", "pdf-image"):
        return f"Conversion not supported for {mode!r} mode."
    else:
        return (
            f"Unknown mode: {mode!r}. "
            f"Valid modes: text, pdf-text, docx, pptx, "
            f"xlsx, pdf-image, pdf-ocr, image."
        )

    # If extract returned an error string, pass it through
    if content.startswith(
        (
            "File not found:",
            "Not a file:",
            "Sheet ",
            "PyMuPDF",
            "python-docx",
            "python-pptx",
            "openpyxl",
            "Invalid pages",
            "Invalid bbox",
            "OCR server",
            "aiohttp",
        )
    ):
        return content
    if content.startswith("Page ") and "out of range" in content:
        return content
    if not content or content == "(empty)":
        return "(empty) — nothing to convert"

    parent = Path(output_dir).resolve() if output_dir else Path(file_path).parent
    stem = Path(file_path).stem
    if mode == "xlsx" and sheet:
        stem = f"{stem}_{sheet}"
    out_path = parent / f"{stem}.txt"
    parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return f"Converted: {file_path} -> {out_path} ({len(content)} chars)"


async def _pdf_ocr_convert(file_path: str, dpi: int | None = None) -> str:
    """OCR the entire PDF via ``_pdf_ocr`` for the convert path.

    Args:
        file_path: Absolute path to the PDF file.
        dpi: Render resolution. Defaults to 150.

    Returns:
        OCR markdown with headers, or an error string.
    """
    try:
        import pymupdf
    except ImportError:
        return "PyMuPDF is not installed. Install it with: pip install PyMuPDF"

    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"

    doc = pymupdf.open(str(path))
    try:
        total_pages = doc.page_count
    finally:
        doc.close()

    return await _pdf_ocr(file_path, f"1-{total_pages}", dpi, "full", None)


async def _read(
    mode: str,
    file_path: str,
    offset: int | None,
    limit: int | None,
    pages: str | None,
    sheet: str | None,
    dpi: int | None,
    submode: str | None,
    bbox: list | None,
    thumb_size: int,
    target: str | None,
) -> str:
    """Dispatch to the appropriate mode reader when convert=False."""
    if mode == "text":
        return await _text(file_path, offset, limit)
    elif mode == "pdf-text":
        return await _pdf_text(file_path, offset, limit)
    elif mode == "docx":
        return await _docx(file_path, offset, limit)
    elif mode == "pptx":
        return await _pptx(file_path, offset, limit)
    elif mode == "pdf-image":
        return await _pdf_image(file_path, pages, dpi, submode, bbox, target)
    elif mode == "pdf-ocr":
        return await _pdf_ocr(file_path, pages, dpi, submode, bbox)
    elif mode == "image":
        return await _image(file_path, submode, dpi, bbox, thumb_size, target)
    elif mode == "xlsx":
        return await _xlsx(file_path, offset, limit, sheet)
    else:
        return (
            f"Unknown mode: {mode!r}. "
            f"Valid modes: text, pdf-text, docx, pptx, "
            f"xlsx, pdf-image, pdf-ocr, image."
        )


if __name__ == "__main__":
    args = json.loads(sys.stdin.read())
    result = asyncio.run(run(**{k: v for k, v in args.items() if v is not None}))
    sys.stdout.reconfigure(encoding="utf-8")
    print(result)
