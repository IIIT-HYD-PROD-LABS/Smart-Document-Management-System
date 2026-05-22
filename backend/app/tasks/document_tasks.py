"""Celery tasks for async document processing."""

import os
import structlog
from celery.exceptions import SoftTimeLimitExceeded
from app.tasks import celery_app
from app.database import SessionLocal
from app.models.document import Document, DocumentStatus, DocumentCategory
from app.config import settings
from app.ml.classifier import extract_and_classify
from app.ml.metadata_extractor import extract_metadata

logger = structlog.stdlib.get_logger()

# Exceptions that will never succeed on retry -- do not waste retries on these.
_NON_RETRYABLE = (ValueError, TypeError, KeyError, AttributeError)


def _safe_set_status(db, doc, status: DocumentStatus, message: str, document_id: int) -> None:
    """Set document status, swallowing DB errors so the caller stays clean."""
    if doc is None:
        return
    try:
        doc.status = status
        doc.extracted_text = message
        db.commit()
    except Exception as commit_err:
        logger.error("status_update_failed", document_id=document_id, error=str(commit_err))
        try:
            db.rollback()
        except Exception:
            pass


def _safe_set_failed(db, doc, message: str, document_id: int) -> None:
    """Convenience wrapper: mark document as FAILED."""
    _safe_set_status(db, doc, DocumentStatus.FAILED, message, document_id)


def _cleanup_file(file_path: str | None) -> None:
    """Remove an uploaded file from disk if it exists. Best-effort, logs errors."""
    if not file_path:
        return
    try:
        from app.services.storage_service import _validate_path_inside_upload_dir
        real_path = _validate_path_inside_upload_dir(file_path)
        os.remove(real_path)
        logger.info("orphan_file_cleaned", filename=os.path.basename(real_path))
    except ValueError:
        logger.warning("cleanup_blocked_path_traversal", path=file_path)
    except FileNotFoundError:
        pass
    except Exception as err:
        logger.warning("orphan_file_cleanup_failed", error=str(err))


def _run_phase17_extraction(
    db, *, document_id: int, notice_id: int, user_id: int | None, extracted_text: str
) -> None:
    """Phase 17 D-23 — extract notice fields when this document attaches to a notice.

    All failure modes mark `extraction_status='failed'` on the notice and
    return; nothing here should re-raise. The Document row is already
    committed by the caller, so partial extraction is acceptable.

    First-upload-wins (D-12): if the notice already carries an accepted
    extraction artefact, skip. A `extracted_supplementary` activity row
    is left behind so the supplementary upload is visible on the timeline.
    """
    try:
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.services.activity_service import log_activity
        from app.compliance.services.extraction_routing_service import (
            apply_extraction_to_notice,
            route_or_apply,
            should_skip_extraction,
        )
        from app.compliance.services.notice_extractor_service import (
            NoticeExtractionCredentialMissingError,
            extract_notice_fields,
        )
    except ImportError as imp_err:
        logger.warning(
            "phase17_extraction_import_failed",
            document_id=document_id,
            error=str(imp_err),
        )
        return

    notice = db.get(ComplianceNotice, notice_id)
    if notice is None:
        return

    if should_skip_extraction(notice):
        try:
            log_activity(
                db,
                notice_id=notice.id,
                user_id=user_id,
                type="file_attached",
                details={"document_id": document_id, "supplementary_extraction_skipped": True},
            )
            db.commit()
        except Exception:
            db.rollback()
        return

    try:
        envelope = extract_notice_fields(
            db,
            client_id=notice.client_id,
            user_id=user_id,
            text=extracted_text or "",
            notice_id=notice.id,
        )
    except NoticeExtractionCredentialMissingError:
        notice.extraction_status = "failed"
        try:
            db.commit()
        except Exception:
            db.rollback()
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "phase17_extraction_failed",
            document_id=document_id,
            notice_id=notice_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        notice.extraction_status = "failed"
        try:
            db.commit()
        except Exception:
            db.rollback()
        return

    try:
        decision = route_or_apply(envelope)
        apply_extraction_to_notice(db, notice, envelope, decision)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "phase17_extraction_apply_failed",
            document_id=document_id,
            notice_id=notice_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        try:
            db.rollback()
        except Exception:
            pass
        notice.extraction_status = "failed"
        try:
            db.commit()
        except Exception:
            db.rollback()


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

        # Stage 1: Read file (with path traversal protection)
        self.update_state(state="PROGRESS", meta={"stage": "reading_file", "progress": 10})
        if doc.file_path:
            from app.services.storage_service import _validate_path_inside_upload_dir
            try:
                validated_path = _validate_path_inside_upload_dir(doc.file_path)
            except ValueError:
                doc.status = DocumentStatus.FAILED
                doc.extracted_text = "File path validation failed."
                db.commit()
                logger.error("path_traversal_blocked_in_task", document_id=document_id)
                return {"error": "Invalid file path"}
            if not os.path.exists(validated_path):
                doc.status = DocumentStatus.FAILED
                doc.extracted_text = "File not found in storage."
                db.commit()
                logger.error("file_not_found", document_id=document_id)
                return {"error": "File not found"}
            file_size = os.path.getsize(validated_path)
            max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            if file_size > max_bytes:
                doc.status = DocumentStatus.FAILED
                doc.extracted_text = f"File too large ({file_size} bytes, max {max_bytes})."
                db.commit()
                logger.error("file_too_large", document_id=document_id, file_size=file_size)
                return {"error": "File too large"}
            with open(validated_path, "rb") as f:
                file_bytes = f.read()
        else:
            doc.status = DocumentStatus.FAILED
            doc.extracted_text = "File not found in storage."
            db.commit()
            logger.error("file_not_found", document_id=document_id)
            return {"error": "File not found"}

        # Stage 2: Extract text and classify
        self.update_state(state="PROGRESS", meta={"stage": "extracting_text", "progress": 30})
        logger.info("processing_document", document_id=document_id, file_type=doc.file_type)

        result = extract_and_classify(file_bytes, doc.file_type)
        # Free raw bytes immediately to reduce memory pressure in the worker
        del file_bytes
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

        # Safely map category string to enum, falling back to UNKNOWN on mismatch
        try:
            doc.category = (
                DocumentCategory(category)
                if category != "unknown"
                else DocumentCategory.UNKNOWN
            )
        except ValueError:
            logger.warning(
                "unknown_category_from_classifier",
                document_id=document_id,
                raw_category=category,
            )
            doc.category = DocumentCategory.UNKNOWN

        doc.confidence_score = confidence
        doc.extracted_metadata = metadata

        if ai_result:
            doc.ai_summary = ai_result.get("summary")
            doc.ai_extracted_fields = ai_result.get("fields")
            doc.ai_provider = ai_result.get("provider")
            # CRIT-5 second hardening — if extract_with_llm fell back to the
            # regex stub because every real provider failed, mark the status
            # distinctly. Operators + UI can show "AI extraction degraded
            # (real providers down — used local stub)" instead of pretending
            # the extraction ran end-to-end.
            if ai_result.get("degraded_local_fallback"):
                doc.ai_extraction_status = "degraded_local"
            else:
                doc.ai_extraction_status = "completed"
        else:
            doc.ai_extraction_status = "skipped"

        doc.status = DocumentStatus.COMPLETED
        db.commit()

        # Phase 17 — when this document is attached to a compliance notice,
        # run LLM field extraction so the notice form gets pre-populated.
        # Non-fatal: a failure leaves extraction_status='failed' and the
        # user falls back to manual entry (D-09 + D-23).
        if getattr(doc, "notice_id", None):
            _run_phase17_extraction(
                db,
                document_id=document_id,
                notice_id=doc.notice_id,
                user_id=getattr(doc, "user_id", None),
                extracted_text=extracted_text,
            )

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
        _safe_set_failed(db, doc, "Processing timed out.", document_id)
        raise

    except _NON_RETRYABLE as e:
        # Permanent failures -- retrying will not help
        logger.error("document_processing_permanent_failure", document_id=document_id, error=str(e), error_type=type(e).__name__)
        _safe_set_failed(db, doc, "Processing failed. Please retry or contact support.", document_id)
        return {"error": str(e), "document_id": document_id, "status": "failed"}

    except Exception as e:
        logger.error("document_processing_failed", document_id=document_id, error=str(e))
        retries_left = self.max_retries - self.request.retries
        if retries_left > 0:
            # Will retry -- keep status as PROCESSING so the UI doesn't
            # flash FAILED between retry attempts.
            _safe_set_status(
                db, doc, DocumentStatus.PROCESSING,
                f"Processing failed, retrying ({retries_left} attempt(s) left)...",
                document_id,
            )
        else:
            # Final attempt exhausted -- mark FAILED and clean up orphaned file.
            _safe_set_failed(db, doc, "Processing failed after all retries. Please re-upload or contact support.", document_id)
            _cleanup_file(getattr(doc, "file_path", None) if doc else None)
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error("max_retries_exceeded", document_id=document_id)
            # Belt-and-suspenders: ensure FAILED is persisted
            _safe_set_failed(db, doc, "Processing failed after all retries. Please re-upload or contact support.", document_id)
            _cleanup_file(getattr(doc, "file_path", None) if doc else None)
            raise

    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()
