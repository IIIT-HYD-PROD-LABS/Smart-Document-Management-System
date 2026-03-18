"""Text preprocessing utilities for ML pipeline."""

import re

import structlog

logger = structlog.stdlib.get_logger()


# Common stop words
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "because", "but", "and",
    "or", "if", "while", "about", "up", "it", "its", "this", "that",
    "i", "me", "my", "we", "our", "you", "your", "he", "his", "she",
    "her", "they", "them", "their", "what", "which", "who", "whom",
}


def clean_text(text: str) -> str:
    """
    Clean and preprocess extracted text for ML classification.
    Steps: lowercase → remove special chars → normalize whitespace → remove stop words.
    """
    if not text:
        return ""

    if len(text) > 500_000:
        logger.warning("clean_text input too long, truncating", original_length=len(text))
        text = text[:500_000]

    # Lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r"https?://[^\s]{1,2000}|www\.[^\s]{1,2000}", " ", text)

    # Remove email addresses
    text = re.sub(r"[^\s]{1,200}@[^\s]{1,200}\.[^\s]{1,200}", " email ", text)

    # Preserve currency and numeric patterns (important for financial docs)
    text = re.sub(r"₹\s?[\d,]+\.?\d*", " rupees_amount ", text)
    text = re.sub(r"\$\s?[\d,]+\.?\d*", " dollar_amount ", text)
    text = re.sub(r"rs\.?\s?[\d,]+\.?\d*", " rupees_amount ", text)

    # Preserve common document identifiers
    text = re.sub(r"invoice\s*#?\s*\d+", " invoice_number ", text)
    text = re.sub(r"bill\s*#?\s*\d+", " bill_number ", text)
    text = re.sub(r"ticket\s*#?\s*\d+", " ticket_number ", text)
    text = re.sub(r"pan\s*[a-z]{5}\d{4}[a-z]", " pan_number ", text)
    text = re.sub(r"gstin?\s*\d{2}[a-z]{5}\d{4}[a-z]\d[a-z\d]{2}", " gst_number ", text)

    # UPI patterns
    text = re.sub(r"\w+@\w+", " upi_id ", text)

    # Remove remaining special characters but keep letters, digits, spaces
    text = re.sub(r"[^a-z0-9\s_]", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove stop words
    words = text.split()
    words = [w for w in words if w not in STOP_WORDS and len(w) > 1]

    return " ".join(words)
