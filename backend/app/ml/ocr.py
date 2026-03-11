"""OCR module - Extract text from images using EasyOCR (deep learning based)."""

from __future__ import annotations

import cv2
import numpy as np
import easyocr
import structlog
from PIL import Image

logger = structlog.stdlib.get_logger()

# Initialize EasyOCR reader once (loads model on first use, reuses after)
# English + Hindi for Indian financial documents
_reader: easyocr.Reader | None = None


def _get_reader() -> easyocr.Reader:
    """Lazy-init the EasyOCR reader (downloads models on first run)."""
    global _reader
    if _reader is None:
        logger.info("easyocr_init", languages=["en", "hi"])
        _reader = easyocr.Reader(["en", "hi"], gpu=False)
    return _reader


def _upscale_if_small(image: np.ndarray, min_height: int = 800) -> np.ndarray:
    """Upscale small images so OCR has enough pixels to work with."""
    h, w = image.shape[:2]
    if h < min_height:
        scale = min_height / h
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return image


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Light preprocessing for EasyOCR.
    EasyOCR has its own internal preprocessing, so we only do upscaling
    and optional contrast enhancement — no aggressive thresholding.
    """
    image = _upscale_if_small(image)

    # Convert to grayscale for CLAHE
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # CLAHE for better contrast on uneven lighting
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    return enhanced


def _easyocr_extract(image: np.ndarray) -> str:
    """Run EasyOCR on an image array and return joined text."""
    reader = _get_reader()
    results = reader.readtext(image, detail=0, paragraph=True)
    return "\n".join(results).strip()


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from image bytes using EasyOCR."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return ""

        # Try both raw and preprocessed, pick the longer result
        preprocessed = preprocess_image(image)
        upscaled = _upscale_if_small(image)

        text_raw = _easyocr_extract(upscaled)
        text_processed = _easyocr_extract(preprocessed)

        best = text_raw if len(text_raw) >= len(text_processed) else text_processed

        logger.info("ocr_extracted", chars=len(best), raw_chars=len(text_raw), processed_chars=len(text_processed))
        return best

    except Exception as e:
        logger.error("ocr_extraction_failed", error=str(e))
        return ""


def extract_text_from_pil_image(pil_image: Image.Image) -> str:
    """Extract text from a PIL Image object."""
    try:
        image = np.array(pil_image)
        if len(image.shape) == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)

        image = _upscale_if_small(image)
        return _easyocr_extract(image)
    except Exception as e:
        logger.error("ocr_pil_extraction_failed", error=str(e))
        return ""
