"""Celery tasks for async document processing."""

import os
from app.tasks import celery_app
from app.database import SessionLocal
from app.models.document import Document, DocumentStatus, DocumentCategory
from app.ml.classifier import extract_and_classify


@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: int):
    """
    Async task to process a document:
    1. Read file from storage
    2. Extract text (OCR / PDF)
    3. Classify document
    4. Update database record
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return {"error": "Document not found"}

        # Update status to processing
        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # Read file bytes
        if doc.file_path and os.path.exists(doc.file_path):
            with open(doc.file_path, "rb") as f:
                file_bytes = f.read()
        else:
            doc.status = DocumentStatus.FAILED
            doc.extracted_text = "File not found in storage."
            db.commit()
            return {"error": "File not found"}

        # Extract text and classify
        extracted_text, category, confidence = extract_and_classify(
            file_bytes, doc.file_type
        )

        # Update document
        doc.extracted_text = extracted_text
        doc.category = (
            DocumentCategory(category)
            if category != "unknown"
            else DocumentCategory.UNKNOWN
        )
        doc.confidence_score = confidence
        doc.status = DocumentStatus.COMPLETED
        db.commit()

        return {
            "document_id": document_id,
            "category": category,
            "confidence": confidence,
            "status": "completed",
        }

    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.extracted_text = f"Processing error: {str(e)}"
        db.commit()
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()
