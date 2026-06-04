"""ML classifier - Load trained model and predict document category."""

import os
import threading

import joblib
import structlog

from app.config import settings
from app.ml.errors import ExtractionEngineError
from app.ml.text_preprocessor import clean_text

logger = structlog.stdlib.get_logger()


MODEL_PATH = os.path.join(settings.MODEL_DIR, "document_classifier.pkl")
VECTORIZER_PATH = os.path.join(settings.MODEL_DIR, "tfidf_vectorizer.pkl")

_model = None
_vectorizer = None
_model_lock = threading.Lock()


def _load_model() -> bool:
    """Lazy-load the trained model and vectorizer.

    Returns True on success. Raises ExtractionEngineError when the artifact
    FILES are missing (a deployment/operational fault the task layer should
    retry), and returns False only on a non-file load failure already logged.
    """
    global _model, _vectorizer
    if _model is not None and _vectorizer is not None:
        return True
    with _model_lock:
        # Double-check after acquiring lock
        if _model is not None and _vectorizer is not None:
            return True
        if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
            try:
                _model = joblib.load(MODEL_PATH)
                _vectorizer = joblib.load(VECTORIZER_PATH)
                logger.info("model_loaded_successfully", model_path=MODEL_PATH, vectorizer_path=VECTORIZER_PATH)
            except Exception as exc:
                logger.error("model_load_failed", error=str(exc), model_path=MODEL_PATH, vectorizer_path=VECTORIZER_PATH)
                return False
        else:
            logger.warning("model_files_not_found", model_dir=settings.MODEL_DIR)
            raise ExtractionEngineError("model_artifacts_missing")
    return True


def classify_document(text: str) -> tuple[str, float]:
    """
    Classify document text into one of the 6 categories.
    Returns (category, confidence_score).
    """
    if not text or len(text.strip()) < 50:
        return "unknown", 0.0

    if not _load_model():
        return "unknown", 0.0

    # Preprocess text
    cleaned = clean_text(text)
    if not cleaned:
        return "unknown", 0.0

    # D3: a model/vectorizer inference failure (corrupt artifact, sklearn
    # version skew, OOM) is transient/operational and must not masquerade as a
    # genuine low-confidence ("unknown", 0.0) result -- that would mark the
    # document permanently FAILED/COMPLETED instead of letting the task layer
    # retry. Re-raise so the distinction is preserved; the legitimate
    # low-confidence branch below still returns "unknown".
    try:
        text_vec = _vectorizer.transform([cleaned])
        prediction = _model.predict(text_vec)[0]
        probabilities = _model.predict_proba(text_vec)[0]
    except Exception as exc:
        logger.error("classification_inference_failed", error=str(exc), error_type=type(exc).__name__)
        raise

    confidence = float(max(probabilities))

    # If confidence is below threshold, return unknown
    if confidence < settings.ML_CONFIDENCE_THRESHOLD:
        return "unknown", confidence

    return prediction, confidence


def extract_and_classify(file_bytes: bytes, file_type: str) -> tuple[str, str, float]:
    """
    Full pipeline: extract text → classify document.
    Returns (extracted_text, category, confidence).
    """
    from app.ml.docx_extractor import extract_text_from_docx
    from app.ml.ocr import extract_text_from_image, extract_text_from_tiff
    from app.ml.pdf_extractor import extract_text_from_pdf

    # Extract text based on file type
    if file_type == "pdf":
        extracted_text = extract_text_from_pdf(file_bytes)
    elif file_type == "docx":
        extracted_text = extract_text_from_docx(file_bytes)
    elif file_type == "txt":
        # D-39: Gmail bodies are persisted as synthetic .txt files;
        # decode directly rather than running OCR.
        try:
            extracted_text = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            extracted_text = ""
    elif file_type in ("tiff", "tif"):
        # H3: cv2.imdecode would drop TIFF pages 2+. Use the frame-iterating
        # path so multi-page scans are fully OCR'd.
        extracted_text = extract_text_from_tiff(file_bytes)
    else:
        extracted_text = extract_text_from_image(file_bytes)

    if not extracted_text:
        return "", "unknown", 0.0

    # Classify
    category, confidence = classify_document(extracted_text)

    return extracted_text, category, confidence
