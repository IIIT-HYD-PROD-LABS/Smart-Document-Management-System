"""OCR module - Extract text from images using Tesseract + OpenCV preprocessing."""

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


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Preprocess image for better OCR accuracy.
    Steps: grayscale → denoise → threshold → deskew.
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Noise removal with Gaussian blur
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)

    # Adaptive thresholding for better contrast
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # Morphological opening to remove small noise spots
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    # Morphological closing to fill small gaps in text
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Deskew
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) > 5:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) > 0.5:
            (h, w) = thresh.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            thresh = cv2.warpAffine(
                thresh, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

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

        # Run OCR with multi-PSM retry
        text = pytesseract.image_to_string(
            processed,
            config="--oem 3 --psm 6",
        )

        # If sparse result, retry with fully automatic page segmentation
        if len(text.strip()) < 20:
            text_auto = pytesseract.image_to_string(
                processed,
                config="--oem 3 --psm 3",
            )
            if len(text_auto.strip()) > len(text.strip()):
                text = text_auto

        return text.strip()

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
