"""Celery tasks for async document processing."""

import os
import structlog
from celery.exceptions import SoftTimeLimitExceeded
from app.tasks import celery_app
from app.database import SessionLocal
from app.models.document import Document, DocumentStatus, DocumentCategory
from app.ml.classifier import extract_and_classify
from app.ml.metadata_extractor import extract_metadata

logger = structlog.stdlib.get_logger()


@celery_app.task(bind=True, max_retries=3, time_limit=600, soft_time_limit=540)
def process_document_task(self, document_id: int):
    """
    Async task to process a document:
    1. Read file from storage
    2. Extract text (OCR / PDF / DOCX)
    3. Classify document
    4. Update database record

    Reports progress stages via self.update_state for frontend polling.
    """
    if not isinstance(document_id, int) or document_id <= 0:
        logger.error("invalid_document_id", document_id=document_id)
        return {"error": "Invalid document_id"}

    db = SessionLocal()
    doc = None
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

        result = extract_and_classify(file_bytes, doc.file_type)
        extracted_text: str = result[0]
        category: str = result[1]
        confidence: float = result[2]

        # Stage 3: Metadata extraction
        self.update_state(state="PROGRESS", meta={"stage": "extracting_metadata", "progress": 50})
        metadata = extract_metadata(extracted_text) if extracted_text else {"dates": [], "amounts": [], "vendor": None}

        # Stage 4: LLM smart extraction
        self.update_state(state="PROGRESS", meta={"stage": "ai_extraction", "progress": 65})
        ai_result = None
        if extracted_text and len(extracted_text.strip()) > 20:
            try:
                from app.services.llm_service import extract_with_llm
                ai_result = extract_with_llm(extracted_text, category)
                logger.info("ai_extraction_completed", document_id=document_id, provider=ai_result.get("provider"))
            except Exception as ai_err:
                logger.warning("ai_extraction_failed", document_id=document_id, error=str(ai_err))

        # Stage 5: Saving results
        self.update_state(state="PROGRESS", meta={"stage": "saving_results", "progress": 85})

        doc.extracted_text = extracted_text
        doc.category = (
            DocumentCategory(category)
            if category != "unknown"
            else DocumentCategory.UNKNOWN
        )
        doc.confidence_score = confidence
        doc.extracted_metadata = metadata

        if ai_result:
            doc.ai_summary = ai_result.get("summary")
            doc.ai_extracted_fields = ai_result.get("fields")
            doc.ai_provider = ai_result.get("provider")
            doc.ai_extraction_status = "completed"
        else:
            doc.ai_extraction_status = "skipped"

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

    except SoftTimeLimitExceeded:
        logger.error("document_processing_timeout", document_id=document_id)
        if doc is not None:
            try:
                doc.status = DocumentStatus.FAILED
                doc.extracted_text = "Processing timed out."
                db.commit()
            except Exception:
                db.rollback()
        raise

    except Exception as e:
        logger.error("document_processing_failed", document_id=document_id, error=str(e))
        if doc is not None:
            try:
                doc.status = DocumentStatus.FAILED
                doc.extracted_text = "Processing failed. Please retry or contact support."
                db.commit()
            except Exception as rollback_err:
                logger.error("status_update_failed", error=str(rollback_err))
                db.rollback()
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error("max_retries_exceeded", document_id=document_id)
            raise

    finally:
        db.rollback()
        db.close()
