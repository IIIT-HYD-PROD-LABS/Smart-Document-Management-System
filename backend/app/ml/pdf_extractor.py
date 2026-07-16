"""PDF text extraction module using pdfplumber with OCR fallback."""

import contextvars
import gc
import io

import pdfplumber
import structlog

from app.ml.errors import ExtractionEngineError
from app.ml.ocr import extract_text_from_pil_image

logger = structlog.stdlib.get_logger()

MAX_PDF_PAGES = 200
# Cap OCR fallback pages to limit memory: rendering 300 DPI images is expensive.
MAX_OCR_FALLBACK_PAGES = 50

# M3: pdfplumber rasterizes each OCR-fallback page at a fixed DPI, so a page with
# adversarially large declared geometry renders to a gigapixel image and
# OOM-kills the worker. Cap the rendered pixel count and lower the DPI for
# oversized page geometry before to_image() allocates the raster.
_OCR_RENDER_DPI = 300
_MAX_OCR_RENDER_PIXELS = 40_000_000

# M4: when a scanned PDF needs OCR on more pages than MAX_OCR_FALLBACK_PAGES,
# the tail is silently skipped. Record that so the task layer can mark the
# document's ai_extraction_status="incomplete_scanned_pdf" (partial, not a
# failure). Reset at the start of each extraction; read immediately after.
_scanned_pdf_truncated: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "scanned_pdf_truncated", default=False
)


def consume_scanned_pdf_truncated() -> bool:
    """Return whether the last PDF extraction hit the OCR page cap, and reset."""
    value = _scanned_pdf_truncated.get()
    _scanned_pdf_truncated.set(False)
    return value


def _safe_render_dpi(page) -> int:
    """Render DPI that keeps a page's rasterized pixel count within the cap.

    A page can declare arbitrarily large geometry; at a fixed DPI that would
    allocate a gigapixel image and exhaust memory. Scale the DPI down so
    width*height stays under _MAX_OCR_RENDER_PIXELS. Falls back to the default
    DPI when the geometry is unavailable.
    """
    try:
        width_px = float(page.width) * _OCR_RENDER_DPI / 72.0
        height_px = float(page.height) * _OCR_RENDER_DPI / 72.0
        projected = width_px * height_px
    except Exception:
        return _OCR_RENDER_DPI
    if projected <= 0 or projected <= _MAX_OCR_RENDER_PIXELS:
        return _OCR_RENDER_DPI
    scale = (_MAX_OCR_RENDER_PIXELS / projected) ** 0.5
    return max(1, int(_OCR_RENDER_DPI * scale))


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF file.
    Uses pdfplumber for text-based PDFs, falls back to OCR for scanned PDFs.
    OCR fallback is capped at MAX_OCR_FALLBACK_PAGES to prevent memory exhaustion
    on large scanned documents.
    """
    _scanned_pdf_truncated.set(False)
    text_parts = []
    ocr_pages_used = 0

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            if total_pages > MAX_PDF_PAGES:
                logger.warning("pdf_page_limit_exceeded", total_pages=total_pages, max_pages=MAX_PDF_PAGES)
            for page in pdf.pages[:MAX_PDF_PAGES]:
                # Try direct text extraction first
                page_text = page.extract_text()

                if page_text and len(page_text.strip()) > 20:
                    text_parts.append(page_text.strip())
                elif ocr_pages_used < MAX_OCR_FALLBACK_PAGES:
                    # Fallback to OCR for scanned pages (memory-bounded)
                    try:
                        page_image = page.to_image(resolution=_safe_render_dpi(page))
                        pil_image = page_image.original
                        ocr_text = extract_text_from_pil_image(pil_image)
                        # Explicitly free the rendered image to reclaim memory
                        del pil_image, page_image
                        if ocr_text:
                            text_parts.append(ocr_text)
                        ocr_pages_used += 1
                    except ExtractionEngineError:
                        # Engine-unavailable (e.g. tesseract missing) is
                        # operational: propagate so the task layer retries
                        # instead of returning a partial/empty body.
                        raise
                    except Exception as ocr_err:
                        logger.warning("pdf_page_ocr_failed", page=page.page_number, error=str(ocr_err))
                        ocr_pages_used += 1
                    # Periodic GC to keep memory bounded across many OCR pages
                    if ocr_pages_used % 10 == 0:
                        gc.collect()
                else:
                    if ocr_pages_used == MAX_OCR_FALLBACK_PAGES:
                        logger.warning(
                            "pdf_ocr_fallback_limit_reached",
                            total_pages=total_pages,
                            ocr_limit=MAX_OCR_FALLBACK_PAGES,
                        )
                        _scanned_pdf_truncated.set(True)
                        ocr_pages_used += 1  # avoid repeat warning

    except ExtractionEngineError:
        raise
    except Exception as e:
        logger.error("pdf_extraction_failed", error=str(e))
        return ""

    return "\n\n".join(text_parts)


def extract_metadata_from_pdf(pdf_bytes: bytes) -> dict:
    """Extract metadata from a PDF file."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            metadata = pdf.metadata or {}
            return {
                "pages": len(pdf.pages),
                "author": metadata.get("Author", ""),
                "title": metadata.get("Title", ""),
                "creator": metadata.get("Creator", ""),
                "created": str(metadata.get("CreationDate", "")),
            }
    except Exception as e:
        logger.warning("pdf_metadata_extraction_failed", error=str(e))
        return {}
