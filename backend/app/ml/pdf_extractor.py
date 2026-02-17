"""PDF text extraction module using pdfplumber with OCR fallback."""

import io
import pdfplumber
from PIL import Image

from app.ml.ocr import extract_text_from_pil_image


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF file.
    Uses pdfplumber for text-based PDFs, falls back to OCR for scanned PDFs.
    """
    text_parts = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                # Try direct text extraction first
                page_text = page.extract_text()

                if page_text and len(page_text.strip()) > 20:
                    text_parts.append(page_text.strip())
                else:
                    # Fallback to OCR for scanned pages
                    page_image = page.to_image(resolution=300)
                    pil_image = page_image.original
                    ocr_text = extract_text_from_pil_image(pil_image)
                    if ocr_text:
                        text_parts.append(ocr_text)

    except Exception as e:
        print(f"PDF extraction error: {e}")
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
    except Exception:
        return {}
