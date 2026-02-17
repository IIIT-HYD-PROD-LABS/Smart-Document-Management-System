"""ML classifier - Load trained model and predict document category."""

import os
import joblib
from app.config import settings
from app.ml.text_preprocessor import clean_text


MODEL_PATH = os.path.join(settings.MODEL_DIR, "document_classifier.pkl")
VECTORIZER_PATH = os.path.join(settings.MODEL_DIR, "tfidf_vectorizer.pkl")

# Category labels
CATEGORIES = ["bills", "upi", "tickets", "tax", "bank", "invoices"]

_model = None
_vectorizer = None


def _load_model():
    """Lazy-load the trained model and vectorizer."""
    global _model, _vectorizer
    if _model is None or _vectorizer is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
            _model = joblib.load(MODEL_PATH)
            _vectorizer = joblib.load(VECTORIZER_PATH)
        else:
            print(f"[WARNING] Model files not found at {settings.MODEL_DIR}. Run training first.")
            return False
    return True


def classify_document(text: str) -> tuple[str, float]:
    """
    Classify document text into one of the 6 categories.
    Returns (category, confidence_score).
    """
    if not text or len(text.strip()) < 5:
        return "unknown", 0.0

    if not _load_model():
        return "unknown", 0.0

    # Preprocess text
    cleaned = clean_text(text)
    if not cleaned:
        return "unknown", 0.0

    # Vectorize
    text_vec = _vectorizer.transform([cleaned])

    # Predict with probability
    prediction = _model.predict(text_vec)[0]
    probabilities = _model.predict_proba(text_vec)[0]
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
    from app.ml.ocr import extract_text_from_image
    from app.ml.pdf_extractor import extract_text_from_pdf

    # Extract text based on file type
    if file_type == "pdf":
        extracted_text = extract_text_from_pdf(file_bytes)
    else:
        extracted_text = extract_text_from_image(file_bytes)

    if not extracted_text:
        return "", "unknown", 0.0

    # Classify
    category, confidence = classify_document(extracted_text)

    return extracted_text, category, confidence
