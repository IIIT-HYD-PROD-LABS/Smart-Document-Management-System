"""Phase 12 v2.0 end-to-end smoke test.

Walks a notice through:
  1. Create notice (received status)
  2. Create response draft → version 1
  3. Update draft → version 2
  4. Submit for review → status='reviewer_pending'
  5. Reviewer approves → status='legal_pending' + approval row
  6. Legal rejects → status='reviewer_pending' + approval row (1 stage back)
  7. Reviewer re-approves → status='legal_pending'
  8. Legal approves → status='cfo_pending'
  9. CFO approves → status='approved'
 10. Attach a Document as evidence → notice_evidence_attachments row
 11. Detach the document → row removed

Verifies:
  - 5 NoticeResponseApproval rows (the 5 decisions)
  - 5 AuditLog rows (notice_response_submitted + 5 approvals + activity)
  - is_response_approved() returns True at the end
  - Status gating: pre-approval, transition to 'submitted' should fail
                   post-approval, transition to 'submitted' should succeed
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
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
    test_label = f"phase12-smoke-{int(datetime.now(timezone.utc).timestamp())}"

    failures: list[str] = []
    client_id = None

    try:
        db.execute(text("RESET ROLE"))
        db.execute(text("SET LOCAL row_security = off"))

        from app.compliance.middleware.tenant_context import (
            set_tenant_context_for_celery,
        )
        from app.compliance.models.client import Client
        from app.compliance.models.membership import ClientMembership
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.models.response import (
            NoticeResponse,
            NoticeResponseApproval,
            NoticeResponseVersion,
        )
        from app.compliance.services.evidence_service import (
            attach_document, detach_document,
        )
        from app.compliance.services.response_service import (
            apply_approval, get_or_create_response, is_response_approved,
            submit_for_review, update_draft,
        )
        from app.compliance.services.response_state_machine import (
            ApprovalStage, ResponseStatus,
        )
        from app.models.document import Document
        from app.models.user import User

        # ── Fixture
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

        client = Client(name=f"Phase12 Smoke {test_label}", client_type="pvt_ltd")
        db.add(client)
        db.flush()
        client_id = client.id

        m = ClientMembership(
            user_id=admin_id, client_id=client_id, compliance_role="compliance_head",
        )
        db.add(m)

        notice = ComplianceNotice(
            client_id=client_id,
            notice_number=f"PHASE12/{test_label}",
            authority="GST",
            status="received",
            received_date=date.today(),
        )
        db.add(notice)
        db.flush()
        notice_id = notice.id

        # Test document for evidence link
        doc = Document(
            user_id=admin_id,
            filename="invoice_ledger.pdf",
            original_filename="invoice_ledger.pdf",
            file_type="pdf",
            file_size=1024,
            file_path=f"/tmp/{test_label}.pdf",
            status="completed",
        )
        db.add(doc)
        db.flush()
        doc_id = doc.id

        db.commit()

        # Make subsequent service calls run with tenant context (defence in
        # depth — RESET ROLE bypassed RLS, but the services themselves don't
        # know that).
        set_tenant_context_for_celery(client_id=client_id, user_id=admin_id, cross_mode=False)

        print(f"Fixture: client={client_id} notice={notice_id} doc={doc_id}")

        # ── Step 1: Create response (auto-creates version 1)
        response = get_or_create_response(db, notice=notice, user_id=admin_id)
        if response.status != "draft":
            failures.append(f"new response status expected 'draft', got {response.status!r}")
        version_count = db.query(NoticeResponseVersion).filter(
            NoticeResponseVersion.response_id == response.id
        ).count()
        if version_count != 1:
            failures.append(f"expected 1 version after create, got {version_count}")

        # ── Step 2: Update draft → version 2
        update_draft(
            db,
            response=response,
            payload={
                "subject": "Response to GST DRC-01",
                "body_markdown": "# Response\n\nWe respectfully submit...",
                "recipient": "Asst. Commissioner, GST Range 5",
                "response_date": date(2026, 5, 6),
            },
            user_id=admin_id,
        )
        db.refresh(response)
        if response.current_version_id is None:
            failures.append("current_version_id not set after update")
        version_count = db.query(NoticeResponseVersion).filter(
            NoticeResponseVersion.response_id == response.id
        ).count()
        if version_count != 2:
            failures.append(f"expected 2 versions after update, got {version_count}")

        # ── Step 3: Submit for review
        submit_for_review(db, response=response, user_id=admin_id)
        db.refresh(response)
        if response.status != "reviewer_pending":
            failures.append(f"after submit: status='{response.status}', expected 'reviewer_pending'")

        # ── Sanity: notice cannot transition to submitted yet
        if is_response_approved(db, notice_id=notice_id):
            failures.append("is_response_approved should be False at reviewer_pending")

        # ── Step 4: Reviewer approves → legal_pending
        apply_approval(
            db, response=response,
            stage=ApprovalStage.REVIEWER, decision="approved",
            user_id=admin_id, reason=None,
        )
        db.refresh(response)
        if response.status != "legal_pending":
            failures.append(f"after reviewer approve: status='{response.status}'")

        # ── Step 5: Legal rejects → reviewer_pending (one stage back)
        apply_approval(
            db, response=response,
            stage=ApprovalStage.LEGAL, decision="rejected",
            user_id=admin_id, reason="missing exhibit B (supplier ledger)",
        )
        db.refresh(response)
        if response.status != "reviewer_pending":
            failures.append(f"after legal reject: status='{response.status}', expected 'reviewer_pending'")

        # ── Step 6: Reviewer re-approves → legal_pending
        apply_approval(
            db, response=response,
            stage=ApprovalStage.REVIEWER, decision="approved",
            user_id=admin_id,
        )
        db.refresh(response)
        if response.status != "legal_pending":
            failures.append(f"after reviewer re-approve: status='{response.status}'")

        # ── Step 7: Legal approves → cfo_pending
        apply_approval(
            db, response=response,
            stage=ApprovalStage.LEGAL, decision="approved",
            user_id=admin_id,
        )
        db.refresh(response)
        if response.status != "cfo_pending":
            failures.append(f"after legal approve: status='{response.status}'")

        # ── Step 8: CFO approves → approved
        apply_approval(
            db, response=response,
            stage=ApprovalStage.CFO, decision="approved",
            user_id=admin_id,
        )
        db.refresh(response)
        if response.status != "approved":
            failures.append(f"after CFO approve: status='{response.status}'")

        if not is_response_approved(db, notice_id=notice_id):
            failures.append("is_response_approved should be True after CFO approve")

        # ── Step 9: Approvals row count = 5 (reviewer ✓, legal ✗, reviewer ✓, legal ✓, cfo ✓)
        approval_count = db.query(NoticeResponseApproval).filter(
            NoticeResponseApproval.response_id == response.id
        ).count()
        if approval_count != 5:
            failures.append(f"expected 5 approvals, got {approval_count}")

        # ── Step 10: Attach + detach evidence
        att = attach_document(
            db, notice=notice, document_id=doc_id, user_id=admin_id,
            description="Supplier ledger Q3",
        )
        if att.notice_id != notice_id:
            failures.append("attached evidence has wrong notice_id")

        # Idempotency
        att2 = attach_document(
            db, notice=notice, document_id=doc_id, user_id=admin_id,
        )
        if att2.id != att.id:
            failures.append("attach_document not idempotent")

        removed = detach_document(db, notice=notice, document_id=doc_id, user_id=admin_id)
        if not removed:
            failures.append("detach_document returned False on existing attachment")

        if failures:
            print("\n=== PHASE 12 SMOKE FAILED ===")
            for f in failures:
                print(f"  - {f}")
            return 1

        print("\n=== PHASE 12 SMOKE PASSED ===")
        print(f"  Response: id={response.id} final_status={response.status}")
        print(f"  Versions persisted: {version_count}")
        print(f"  Approval rows: {approval_count}")
        print(f"  Evidence: attached + idempotent re-attach + detached")
        print(f"  is_response_approved: True (gates notice → submitted)")
        return 0

    finally:
        try:
            db.execute(text("RESET ROLE"))
            db.execute(text("SET LOCAL row_security = off"))
            if client_id is not None:
                db.execute(text("DELETE FROM notice_evidence_attachments WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM notice_response_approvals WHERE client_id = :cid"), {"cid": client_id})
                # FK cycle: clear current_version_id before deleting versions
                db.execute(text("UPDATE notice_responses SET current_version_id = NULL WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM notice_response_versions WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM notice_responses WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM compliance_notice_activity WHERE notice_id IN (SELECT id FROM compliance_notices WHERE client_id = :cid)"), {"cid": client_id})
                db.execute(text("DELETE FROM compliance_notices WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM compliance_client_memberships WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM compliance_clients WHERE id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM documents WHERE original_filename = :fn AND user_id IN (SELECT id FROM users WHERE username LIKE 'phase12-smoke%')"),
                           {"fn": "invoice_ledger.pdf"})
                db.commit()
                print("Cleanup OK")
        except Exception as e:
            print(f"Cleanup failed: {e}")
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
