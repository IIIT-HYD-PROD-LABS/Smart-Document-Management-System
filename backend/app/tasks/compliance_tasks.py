"""Phase 10 Celery tasks — routed to the compliance queue (2GB worker).

Per CONTEXT D-23, the inference pipeline runs as a single Celery task to avoid
serialization overhead between stages:

  extract_text (v1.0 OCR) → regex_extract → ner_extract → authority_classify →
  type_classify(authority) → feature_engineer → risk_score → escalation_check →
  persist

Triggered automatically on ComplianceNotice transition Received → Under Review
(per CONTEXT note: anti-pattern to auto-classify Resolved/Dismissed notices).
"""

from __future__ import annotations

import logging
from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.compliance_tasks.classify_and_score_notice",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def classify_and_score_notice(self, notice_id: int) -> dict:
    """Full pipeline for a single notice: classification + NER + risk + escalation.

    Args:
        notice_id: ComplianceNotice.id

    Returns:
        dict with classification, extracted fields, risk score, and escalation decision

    NOTE: Phase 10 Wave 0 skeleton. Implementation lands in Plan 10-XX after
    BERT model selection (/gsd:research-phase 10) and training (/gsd:plan-phase 10
    → /gsd:execute-phase 10).
    """
    raise NotImplementedError(
        f"Phase 10 pipeline not yet implemented for notice {notice_id}. "
        "Pending /gsd:plan-phase 10 + /gsd:execute-phase 10."
    )


@celery_app.task(
    name="app.tasks.compliance_tasks.recompute_all_risk_scores",
    bind=True,
)
def recompute_all_risk_scores(self) -> dict:
    """Daily cron — recompute risk scores for all open notices.

    Per CONTEXT D-16: deadline-relative risk drifts as the deadline approaches.
    Triggered by APScheduler (Phase 11 INFRA-04) at 02:00 IST.
    Re-escalates if any Medium notice crosses to Critical due to deadline proximity.
    """
    raise NotImplementedError("Pending Phase 10 + Phase 11 integration.")
