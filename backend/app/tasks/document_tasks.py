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

        # Stage 3: Metadata extraction (regex-based)
        self.update_state(state="PROGRESS", meta={"stage": "extracting_metadata", "progress": 50})
        metadata = extract_metadata(extracted_text) if extracted_text else {"dates": [], "amounts": [], "vendor": None}

        # Stage 4: LLM extraction (if user has provider configured)
        self.update_state(state="PROGRESS", meta={"stage": "ai_extraction", "progress": 70})
        ai_summary = None
        ai_extracted_data = None
        extraction_status = None

        if extracted_text and len(extracted_text.strip()) > 50:
            try:
                from app.models.user_settings import UserLLMSettings

                user_settings = db.query(UserLLMSettings).filter(
                    UserLLMSettings.user_id == doc.user_id
                ).first()

                if user_settings and user_settings.api_key_encrypted:
                    extraction_status = "processing"
                    api_key = user_settings.decrypt_api_key()
                    if api_key:
                        from app.services.llm import extract_with_llm

                        result = extract_with_llm(
                            text=extracted_text,
                            category=category,
                            provider=user_settings.llm_provider,
                            api_key=api_key,
                            model_name=user_settings.model_name,
                        )
                        ai_summary = result.summary if result.summary else None
                        ai_extracted_data = result.model_dump(mode="json")
                        extraction_status = "completed"
                        logger.info(
                            "llm_extraction_completed",
                            document_id=document_id,
                            provider=user_settings.llm_provider,
                            overall_confidence=result.overall_confidence,
                        )
                    else:
                        extraction_status = "failed"
                        logger.warning(
                            "llm_extraction_failed",
                            document_id=document_id,
                            reason="api_key_decrypt_failed",
                        )
                else:
                    logger.info(
                        "llm_extraction_skipped",
                        document_id=document_id,
                        reason="no_settings",
                    )
            except Exception as llm_err:
                extraction_status = "failed"
                logger.warning(
                    "llm_extraction_failed",
                    document_id=document_id,
                    error=str(llm_err),
                    error_type=type(llm_err).__name__,
                )

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
        doc.ai_summary = ai_summary
        doc.ai_extracted_data = ai_extracted_data
        doc.extraction_status = extraction_status
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
        if doc is not None:
            try:
                doc.status = DocumentStatus.FAILED
                doc.extracted_text = f"Processing error: {e}"
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
        db.close()
