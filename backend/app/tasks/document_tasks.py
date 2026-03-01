"""Celery tasks for async document processing."""

import os
import structlog
from app.tasks import celery_app
from app.database import SessionLocal
from app.models.document import Document, DocumentStatus, DocumentCategory
from app.ml.classifier import extract_and_classify
from app.ml.metadata_extractor import extract_metadata

logger = structlog.stdlib.get_logger()


@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: int):
    """
    Async task to process a document:
    1. Read file from storage
    2. Extract text (OCR / PDF / DOCX)
    3. Classify document
    4. Update database record

    Reports progress stages via self.update_state for frontend polling.
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error("document_not_found", document_id=document_id)
            return {"error": "Document not found"}

        # Update status to processing
        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # Stage 1: Read file
        self.update_state(state="PROGRESS", meta={"stage": "reading_file", "progress": 10})
        if doc.file_path and os.path.exists(doc.file_path):
            with open(doc.file_path, "rb") as f:
                file_bytes = f.read()
        else:
            doc.status = DocumentStatus.FAILED
            doc.extracted_text = "File not found in storage."
            db.commit()
            logger.error("file_not_found", document_id=document_id, file_path=doc.file_path)
            return {"error": "File not found"}

        # Stage 2: Extract text and classify
        self.update_state(state="PROGRESS", meta={"stage": "extracting_text", "progress": 30})
        logger.info("processing_document", document_id=document_id, file_type=doc.file_type)

        extracted_text, category, confidence = extract_and_classify(
            file_bytes, doc.file_type
        )

        # Stage 3: Metadata extraction
        self.update_state(state="PROGRESS", meta={"stage": "extracting_metadata", "progress": 60})
        metadata = extract_metadata(extracted_text) if extracted_text else {"dates": [], "amounts": [], "vendor": None}

        # Stage 4: Saving results
        self.update_state(state="PROGRESS", meta={"stage": "saving_results", "progress": 80})

        doc.extracted_text = extracted_text
        doc.category = (
            DocumentCategory(category)
            if category != "unknown"
            else DocumentCategory.UNKNOWN
        )
        doc.confidence_score = confidence
        doc.extracted_metadata = metadata
        doc.status = DocumentStatus.COMPLETED
        db.commit()

        logger.info(
            "document_processed",
            document_id=document_id,
            category=category,
            confidence=confidence,
        )

        return {
            "document_id": document_id,
            "category": category,
            "confidence": confidence,
            "metadata": metadata,
            "status": "completed",
        }

    except Exception as e:
        logger.error("document_processing_failed", document_id=document_id, error=str(e))
        try:
            doc.status = DocumentStatus.FAILED
            doc.extracted_text = f"Processing error: {str(e)}"
            db.commit()
        except Exception:
            db.rollback()
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    finally:
        db.close()
