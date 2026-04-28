"""Phase 10 Celery tasks — routed to the compliance queue (2GB worker).

Per CONTEXT D-23, the inference pipeline runs as a single Celery task to avoid
serialization overhead between stages:

  extract_text (v1.0 OCR) → regex_extract → ner_extract → authority_classify →
  type_classify(authority) → feature_engineer → risk_score → escalation_check →
  persist

Triggered automatically on ComplianceNotice transition Received → Under Review
via notice_service.transition_notice_status.

Current state (2026-04-28): rule-based risk scorer (model_version='rules-v1.0')
is the production scorer. BERT classifier is scaffolded but not yet trained;
NER beyond regex_patterns is scaffolded but not yet trained. The task gracefully
degrades — what's working today produces a real risk score + extracted regex
fields. BERT/NER fields populate as those models become available.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.compliance_tasks.classify_and_score_notice",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def classify_and_score_notice(self, notice_id: int) -> dict:
    """Full Phase 10 pipeline for a single notice.

    Steps (current state of each):
      1. Load notice + extract document text via v1.0 OCR — IMPLEMENTED
      2. Regex extraction (GSTIN, PAN, CIN, sections) — IMPLEMENTED
      3. spaCy NER — STUB (CONTEXT D-08..D-12; awaiting custom training)
      4. BERT authority classification — STUB (CONTEXT D-01; awaiting fine-tune)
      5. BERT type classification — STUB (CONTEXT D-02..D-03; awaiting fine-tune)
      6. Rule-based risk scoring — IMPLEMENTED (CONTEXT D-13..D-17)
      7. Escalation event emit (Critical only) — STUB (Phase 11 dep)
      8. Persist results to compliance_notices columns — IMPLEMENTED

    Args:
        notice_id: ComplianceNotice.id

    Returns:
        dict summary of what was computed and persisted.
    """
    # Lazy imports — avoid pulling SQLAlchemy/torch into worker bootstrap.
    from app.compliance.models.notice import ComplianceNotice
    from app.database import SessionLocal
    from app.ml.compliance import regex_patterns, risk_scorer

    db = SessionLocal()
    try:
        notice = db.get(ComplianceNotice, notice_id)
        if notice is None:
            logger.warning("classify_and_score_notice: notice %d not found", notice_id)
            return {"error": "notice_not_found", "notice_id": notice_id}

        # Step 1: Aggregate all available text. Future-proof: when document
        # OCR text is available we'll have a much richer corpus to mine.
        text_parts: list[str] = []
        if notice.notice_number:
            text_parts.append(notice.notice_number)
        if notice.legal_sections:
            text_parts.extend(str(s) for s in notice.legal_sections)
        if notice.document_id:
            from app.models.document import Document

            doc = db.get(Document, notice.document_id)
            if doc and doc.extracted_text:
                text_parts.append(doc.extracted_text)
        full_text = " ".join(text_parts)

        # Step 2: Regex-first extraction (CLASS-06).
        ner_extracted = {
            "gstins": regex_patterns.extract_gstins(full_text),
            "pans": regex_patterns.extract_pans(full_text),
            "cins": regex_patterns.extract_cins(full_text),
            "section_references": regex_patterns.extract_section_references(full_text),
            # spaCy NER additions land here when trained:
            # "deadline_dates": [...],
            # "penalty_amounts": [...],
            "regex_extractor_version": "v1.0",
        }

        # Step 3-5: BERT + spaCy NER stubs — populate when models are trained.
        # For now, the manual authority/type entered at upload is authoritative.
        bert_classification = None  # noqa: F841 — placeholder for future BERT integration

        # Step 6: Rule-based risk scoring (real, working).
        merged_sections = list(notice.legal_sections or [])
        merged_sections.extend(ner_extracted["section_references"])
        # Deduplicate while preserving order.
        seen: set = set()
        deduped_sections = [
            s for s in merged_sections if not (s in seen or seen.add(s))
        ]

        has_show_cause_chain = False
        if notice.parent_notice_id is not None:
            parent = db.get(ComplianceNotice, notice.parent_notice_id)
            if parent and parent.notice_type and parent.notice_type.code:
                code_upper = parent.notice_type.code.upper()
                has_show_cause_chain = code_upper.startswith(("SCN", "SHOW"))

        assessment = risk_scorer.score(
            authority=notice.authority,
            penalty_amount=notice.penalty,
            tax_demand=notice.tax_demand,
            deadline=notice.response_deadline,
            today=date.today(),
            legal_sections=deduped_sections,
            has_show_cause_chain=has_show_cause_chain,
        )

        # Step 8: Persist results to compliance_notices.
        now = datetime.now(timezone.utc)
        notice.risk_score = Decimal(str(assessment.score))
        notice.risk_tier = assessment.tier
        notice.model_version = assessment.model_version
        notice.ner_extracted_fields = ner_extracted
        notice.classified_at = now
        notice.risk_scored_at = now
        # NOTE: classifier_authority_confidence + classifier_type_confidence
        # remain NULL until the BERT classifier ships.
        db.commit()
        db.refresh(notice)

        # Step 7: Escalation hook (Phase 11 dep — emits event, no-op for now).
        if assessment.tier == "critical":
            logger.info(
                "Notice %d hit Critical tier (score=%.2f) — escalation event "
                "would fire here once Phase 11 alert pipeline is wired",
                notice_id, assessment.score,
            )
            # TODO(Phase 11): emit NOTICE_ESCALATION event to alert pipeline
            # TODO(Phase 11): assign to compliance_head queue per client config

        result = {
            "notice_id": notice_id,
            "risk_score": float(assessment.score),
            "risk_tier": assessment.tier,
            "model_version": assessment.model_version,
            "top_factors": [
                {
                    "feature": f.feature,
                    "contribution": round(f.contribution, 2),
                    "phrase": f.natural_language,
                }
                for f in assessment.top_factors
            ],
            "ner_extracted_fields": ner_extracted,
            "bert_classification": "pending_fine_tune",
            "computed_at": now.isoformat(),
        }
        logger.info(
            "Classified notice %d: score=%.1f tier=%s model=%s",
            notice_id, assessment.score, assessment.tier, assessment.model_version,
        )
        return result

    except Exception as exc:
        logger.exception("classify_and_score_notice failed for notice %d", notice_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": "retries_exhausted", "notice_id": notice_id, "exc": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.compliance_tasks.recompute_all_risk_scores",
    bind=True,
)
def recompute_all_risk_scores(self) -> dict:
    """Daily cron — recompute risk scores for all open notices.

    Per CONTEXT D-16: deadline-relative risk drifts as the deadline approaches.
    Triggered by APScheduler (Phase 11 INFRA-04) at 02:00 IST.
    Re-escalates if any Medium notice crosses to Critical due to deadline proximity.

    Implementation: dispatches one classify_and_score_notice task per open
    notice rather than doing the work inline. This lets the existing retry +
    rate-limit semantics apply and keeps this task short.
    """
    from sqlalchemy import select

    from app.compliance.models.notice import ComplianceNotice
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        # Only open statuses participate in daily recompute.
        open_statuses = ("received", "under_review", "response_drafted")
        stmt = select(ComplianceNotice.id).where(
            ComplianceNotice.status.in_(open_statuses)
        )
        notice_ids = [row[0] for row in db.execute(stmt).all()]
    finally:
        db.close()

    dispatched = 0
    for nid in notice_ids:
        classify_and_score_notice.delay(nid)
        dispatched += 1

    logger.info("recompute_all_risk_scores: dispatched %d notice tasks", dispatched)
    return {"dispatched": dispatched, "open_statuses": list(open_statuses)}
