"""OCR module - Extract text from images using Tesseract + OpenCV preprocessing."""

from __future__ import annotations

import cv2
import numpy as np
import pytesseract
import structlog
from PIL import Image

from app.config import settings

logger = structlog.stdlib.get_logger()


# Configure Tesseract path if provided
if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def _upscale_if_small(image: np.ndarray, min_height: int = 800) -> np.ndarray:
    """Upscale small images so Tesseract has enough pixels to work with."""
    h, w = image.shape[:2]
    if h < min_height:
        scale = min_height / h
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return image


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct slight rotation in scanned documents."""
    coords = np.column_stack(np.where(image > 0))
    if len(coords) < 10:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > 0.5:
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        image = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
    return image


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Preprocess image for better OCR accuracy.
    Steps: upscale → grayscale → denoise → CLAHE contrast → Otsu threshold → deskew.
    """
    # Upscale small/low-res images
    image = _upscale_if_small(image)

    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Bilateral filter preserves edges better than Gaussian for document text
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # CLAHE (adaptive histogram equalization) for better contrast on uneven lighting
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Otsu's thresholding — automatically picks the best threshold value
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morphological opening to remove small noise spots
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    # Deskew
    thresh = _deskew(thresh)

    return thresh


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from image bytes using Tesseract OCR with preprocessing."""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return ""

        # Preprocess
        processed = preprocess_image(image)

        # Try multiple PSM modes and pick the best result
        best_text = ""
        for psm in (6, 3, 4):  # block, auto, single-column
            candidate = pytesseract.image_to_string(
                processed,
                config=f"--oem 3 --psm {psm}",
            ).strip()
            if len(candidate) > len(best_text):
                best_text = candidate

        # Also try on the original (unprocessed) grayscale — sometimes preprocessing
        # hurts more than it helps on clean images
        if len(image.shape) == 3:
            gray_orig = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray_orig = image
        gray_orig = _upscale_if_small(gray_orig)
        raw_text = pytesseract.image_to_string(
            gray_orig, config="--oem 3 --psm 3"
        ).strip()
        if len(raw_text) > len(best_text):
            best_text = raw_text

        return best_text

    except Exception as e:
        logger.error("ocr_extraction_failed", error=str(e))
        return ""


def extract_text_from_pil_image(pil_image: Image.Image) -> str:
    """Extract text from a PIL Image object."""
    try:
        # Convert to numpy array
        image = np.array(pil_image)
        if len(image.shape) == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)

        processed = preprocess_image(image)
        text = pytesseract.image_to_string(processed, config="--oem 3 --psm 6")
        return text.strip()
    except Exception as e:
        logger.error("ocr_pil_extraction_failed", error=str(e))
        return ""
