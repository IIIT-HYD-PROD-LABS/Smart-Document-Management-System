"""PDF text extraction module using pdfplumber with OCR fallback."""

import gc
import io

import pdfplumber
import structlog

from app.ml.ocr import extract_text_from_pil_image

logger = structlog.stdlib.get_logger()

MAX_PDF_PAGES = 200
# Cap OCR fallback pages to limit memory: rendering 300 DPI images is expensive.
MAX_OCR_FALLBACK_PAGES = 50


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF file.
    Uses pdfplumber for text-based PDFs, falls back to OCR for scanned PDFs.
    OCR fallback is capped at MAX_OCR_FALLBACK_PAGES to prevent memory exhaustion
    on large scanned documents.
    """
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
                        page_image = page.to_image(resolution=300)
                        pil_image = page_image.original
                        ocr_text = extract_text_from_pil_image(pil_image)
                        # Explicitly free the rendered image to reclaim memory
                        del pil_image, page_image
                        if ocr_text:
                            text_parts.append(ocr_text)
                        ocr_pages_used += 1
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
                        ocr_pages_used += 1  # avoid repeat warning

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
