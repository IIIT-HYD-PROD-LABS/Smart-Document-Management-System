"""Unified notice pipeline: Document intelligence → Compliance surfaces.

Single entry points so email, Drive, manual upload, and future portal
exports all follow the same post-OCR path:

  OCR/classify → Phase 17 field extract → process_notice_intake
    (risk score + deadline alerts → calendar/audit/reports consumers)
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def after_document_intelligence(
    db: Session,
    *,
    document_id: int,
    notice_id: Optional[int],
    user_id: Optional[int],
    extracted_text: str,
) -> dict:
    """Run after OCR + category classification complete on a document.

    When the document is linked to a compliance notice:
      1. Phase 17 extraction fills empty notice columns from OCR text
         (critical for PDF-only emails with empty bodies).
      2. process_notice_intake re-dispatches risk scoring and schedules
         deadline alerts so the calendar picks up PDF-extracted dates.

    Returns a small status dict for logs/tests. Never raises to callers
    that want best-effort behaviour — exceptions are logged and folded
    into the return value.
    """
    status: dict = {
        "document_id": document_id,
        "notice_id": notice_id,
        "extraction": "skipped",
        "intake": "skipped",
    }
    if not notice_id:
        return status
    if not (extracted_text or "").strip():
        status["extraction"] = "no_text"
        return status

    try:
        from app.tasks.document_tasks import _run_phase17_extraction

        _run_phase17_extraction(
            db,
            document_id=document_id,
            notice_id=notice_id,
            user_id=user_id,
            extracted_text=extracted_text,
        )
        status["extraction"] = "ran"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pipeline_phase17_failed document_id=%s notice_id=%s err=%s",
            document_id,
            notice_id,
            exc,
        )
        status["extraction"] = f"failed:{type(exc).__name__}"

    # Re-load notice so intake sees any deadline filled by extraction.
    try:
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.services.notice_service import process_notice_intake

        notice = db.get(ComplianceNotice, notice_id)
        if notice is None:
            status["intake"] = "notice_missing"
            return status
        deadline = getattr(notice, "response_deadline", None)
        nid = int(getattr(notice, "id"))
        process_notice_intake(nid, deadline)
        status["intake"] = "dispatched"
        status["response_deadline"] = str(deadline) if deadline else None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pipeline_intake_failed document_id=%s notice_id=%s err=%s",
            document_id,
            notice_id,
            exc,
        )
        status["intake"] = f"failed:{type(exc).__name__}"

    return status
