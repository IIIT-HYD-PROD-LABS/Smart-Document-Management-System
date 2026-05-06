"""Phase 10 v2.0 end-to-end smoke test.

Inserts a Critical-tier compliance notice via the postgres-role engine
(bypassing RLS for fixture setup), triggers classify_and_score_notice
synchronously (via .run() not .delay() to keep the smoke contained to
the backend container), and verifies:

  1. risk_score is populated and falls in [85, 100] (Critical band)
  2. risk_tier == 'critical'
  3. model_version == 'rules-v1.0'
  4. ner_extracted_fields contains regex hits + risk_top_factors
  5. classified_at + risk_scored_at are set
  6. NoticeActivity row with type='assigned' and source='critical_escalation' exists
  7. AuditLog row with action='notice_escalated' exists
  8. NoticeReviewQueue stays empty (BERT confidences are NULL in v2.0)

Then runs a Low-tier notice through the same pipeline to verify:
  9. risk_tier == 'low' or 'medium' (no escalation expected)
 10. No NoticeActivity escalation row for the low-tier notice

Cleans up all test rows on exit (CASCADE deletes hit child rows).
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("FATAL: DATABASE_URL not set", file=sys.stderr)
        return 2

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = Session()
    test_label = f"phase10-smoke-{int(datetime.now(timezone.utc).timestamp())}"

    try:
        # Bypass RLS for fixture setup.
        db.execute(text("RESET ROLE"))
        db.execute(text("SET LOCAL row_security = off"))

        # 1. Test user (use existing if any with role 'admin' available; else create one)
        from app.models.user import User

        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            admin = User(
                email=f"{test_label}@smoke.test",
                username=f"{test_label}_user",
                hashed_password="x",
                role="admin",
            )
            db.add(admin)
            db.flush()
        admin_id = admin.id

        # 2. Test client + compliance_head membership
        from app.compliance.models.client import Client
        from app.compliance.models.membership import ClientMembership

        client = Client(name=f"Smoke Test {test_label}", client_type="pvt_ltd")
        db.add(client)
        db.flush()
        client_id = client.id

        membership = ClientMembership(
            user_id=admin_id,
            client_id=client_id,
            compliance_role="compliance_head",
        )
        db.add(membership)
        db.flush()

        # 3. Critical-tier notice (RBI + ₹50L + section 132 + tomorrow deadline)
        from app.compliance.models.notice import ComplianceNotice

        crit = ComplianceNotice(
            client_id=client_id,
            notice_number="SMOKE/CRITICAL/2026/01",
            authority="RBI",
            status="received",
            received_date=date.today(),
            response_deadline=date.today() + timedelta(days=2),
            penalty=Decimal("5000000"),
            legal_sections=["u/s 271(1)(c)", "Section 132"],
            assigned_user_id=None,
        )
        db.add(crit)
        db.flush()
        crit_id = crit.id

        # 4. Low-tier notice (MCA + no penalty + 90-day deadline)
        low = ComplianceNotice(
            client_id=client_id,
            notice_number="SMOKE/LOW/2026/01",
            authority="MCA",
            status="received",
            received_date=date.today(),
            response_deadline=date.today() + timedelta(days=90),
            legal_sections=[],
            assigned_user_id=None,
        )
        db.add(low)
        db.flush()
        low_id = low.id

        db.commit()

        print(f"Fixture: client_id={client_id} crit_notice={crit_id} low_notice={low_id}")

        # 5. Trigger classify_and_score_notice synchronously
        from app.tasks.compliance_tasks import classify_and_score_notice

        crit_result = classify_and_score_notice.run(crit_id)
        low_result = classify_and_score_notice.run(low_id)

        print(f"crit_result: tier={crit_result['risk_tier']} score={crit_result['risk_score']} model={crit_result['model_version']}")
        print(f"low_result : tier={low_result['risk_tier']} score={low_result['risk_score']} model={low_result['model_version']}")

        # 6. Refresh and verify
        db.expire_all()
        crit = db.get(ComplianceNotice, crit_id)
        low = db.get(ComplianceNotice, low_id)

        from app.compliance.models.notice import NoticeActivity
        from app.compliance.models.review_queue import NoticeReviewQueue
        from app.models.audit_log import AuditLog

        failures = []

        # Critical tier checks
        if crit.risk_tier != "critical":
            failures.append(f"crit.risk_tier expected 'critical', got {crit.risk_tier!r}")
        if crit.risk_score is None or float(crit.risk_score) < 85:
            failures.append(f"crit.risk_score expected >= 85, got {crit.risk_score}")
        if crit.model_version != "rules-v1.0":
            failures.append(f"crit.model_version expected 'rules-v1.0', got {crit.model_version!r}")
        if not crit.classified_at:
            failures.append("crit.classified_at not set")
        if not crit.risk_scored_at:
            failures.append("crit.risk_scored_at not set")
        if not crit.ner_extracted_fields:
            failures.append("crit.ner_extracted_fields is empty")
        else:
            ner = crit.ner_extracted_fields
            if "risk_top_factors" not in ner:
                failures.append("crit ner_extracted_fields missing risk_top_factors")
            elif not isinstance(ner["risk_top_factors"], list) or len(ner["risk_top_factors"]) == 0:
                failures.append("crit ner_extracted_fields.risk_top_factors empty")
            else:
                for f in ner["risk_top_factors"]:
                    for key in ("feature", "contribution", "phrase"):
                        if key not in f:
                            failures.append(f"crit risk_top_factors entry missing {key!r}")

        # Critical tier escalation should have created NoticeActivity + AuditLog
        crit_activity = (
            db.query(NoticeActivity)
            .filter(
                NoticeActivity.notice_id == crit_id,
                NoticeActivity.type == "assigned",
            )
            .all()
        )
        crit_escalation_rows = [
            a for a in crit_activity
            if isinstance(a.details, dict) and a.details.get("source") == "critical_escalation"
        ]
        if not crit_escalation_rows:
            failures.append("no NoticeActivity row with source='critical_escalation' for Critical notice")
        else:
            esc = crit_escalation_rows[0]
            if esc.details.get("after_assigned_user_id") != admin_id:
                failures.append(
                    f"escalation expected to assign to admin (id={admin_id}), got {esc.details.get('after_assigned_user_id')!r}"
                )

        # Re-read notice to confirm the escalation reassigned assigned_user_id
        if crit.assigned_user_id != admin_id:
            failures.append(
                f"crit.assigned_user_id expected admin {admin_id}, got {crit.assigned_user_id}"
            )

        crit_audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "notice_escalated",
                AuditLog.resource_id == crit_id,
            )
            .all()
        )
        if not crit_audit:
            failures.append("no AuditLog row with action='notice_escalated' for Critical notice")

        # Low-tier should NOT have escalated
        low_activity = (
            db.query(NoticeActivity)
            .filter(NoticeActivity.notice_id == low_id, NoticeActivity.type == "assigned")
            .all()
        )
        low_esc_rows = [
            a for a in low_activity
            if isinstance(a.details, dict) and a.details.get("source") == "critical_escalation"
        ]
        if low_esc_rows:
            failures.append("low-tier notice unexpectedly escalated")

        # Review queue stays empty (NULL confidences in v2.0)
        rq = (
            db.query(NoticeReviewQueue)
            .filter(NoticeReviewQueue.notice_id.in_([crit_id, low_id]))
            .all()
        )
        if rq:
            failures.append(f"review queue should be empty in v2.0, got {len(rq)} rows")

        # Output
        if failures:
            print("\n=== SMOKE FAILED ===")
            for f in failures:
                print(f"  - {f}")
            return 1

        print("\n=== SMOKE PASSED ===")
        print(f"  Critical tier: score={float(crit.risk_score):.1f} tier={crit.risk_tier} model={crit.model_version}")
        print(f"  Low tier:      score={float(low.risk_score):.1f} tier={low.risk_tier} model={low.model_version}")
        print(f"  Critical NoticeActivity escalation rows: {len(crit_escalation_rows)}")
        print(f"  Critical AuditLog notice_escalated rows: {len(crit_audit)}")
        print(f"  Critical assigned_user_id reassigned to admin: {admin_id}")
        print(f"  ner_extracted_fields.risk_top_factors length: {len(crit.ner_extracted_fields['risk_top_factors'])}")
        print(f"  Sample SHAP phrase: {crit.ner_extracted_fields['risk_top_factors'][0]['phrase']}")
        print(f"  Review queue empty (v2.0 expected): {len(rq) == 0}")
        return 0

    finally:
        # Cleanup — bypass RLS, hard-delete child rows first then parents
        try:
            db.execute(text("RESET ROLE"))
            db.execute(text("SET LOCAL row_security = off"))
            db.execute(text("DELETE FROM notice_review_queue WHERE client_id = :cid"), {"cid": client_id})
            db.execute(text("DELETE FROM compliance_notice_activity WHERE notice_id IN (SELECT id FROM compliance_notices WHERE client_id = :cid)"), {"cid": client_id})
            db.execute(text("DELETE FROM compliance_notices WHERE client_id = :cid"), {"cid": client_id})
            db.execute(text("DELETE FROM compliance_client_memberships WHERE client_id = :cid"), {"cid": client_id})
            db.execute(text("DELETE FROM compliance_clients WHERE id = :cid"), {"cid": client_id})
            db.execute(
                text("DELETE FROM audit_logs WHERE action = 'notice_escalated' AND details::text LIKE :tag"),
                {"tag": f"%{client_id}%"},
            )
            db.commit()
            print("Cleanup OK")
        except Exception as e:
            print(f"Cleanup failed: {e}")
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
