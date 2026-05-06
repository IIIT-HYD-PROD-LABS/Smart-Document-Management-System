"""Phase 13 v2.0 end-to-end smoke test for unified search + report aggregations.

Inserts:
  - 1 Client + 1 Membership
  - 3 ComplianceNotices with diverse authorities/statuses/penalties
  - 2 Documents with extracted_text
Then exercises:
  - unified_search_service.search() → both notice + document hits
  - report_service.penalty_by_authority()
  - report_service.notice_volume_by_status()
  - report_service.response_time_distribution()

Cleans up on exit.
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
    test_label = f"phase13-smoke-{int(datetime.now(timezone.utc).timestamp())}"
    failures: list[str] = []
    client_id = None
    notice_ids: list[int] = []
    doc_ids: list[int] = []

    try:
        db.execute(text("RESET ROLE"))
        db.execute(text("SET LOCAL row_security = off"))

        from app.compliance.middleware.tenant_context import (
            set_tenant_context_for_celery,
        )
        from app.compliance.models.client import Client
        from app.compliance.models.membership import ClientMembership
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.services.report_service import (
            notice_volume_by_status,
            penalty_by_authority,
            response_time_distribution,
        )
        from app.compliance.services.unified_search_service import search
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

        client = Client(name=f"Phase13 Smoke {test_label}", client_type="pvt_ltd")
        db.add(client)
        db.flush()
        client_id = client.id

        m = ClientMembership(
            user_id=admin_id, client_id=client_id, compliance_role="compliance_head",
        )
        db.add(m)

        # 3 notices spanning authorities + statuses
        n1 = ComplianceNotice(
            client_id=client_id,
            notice_number=f"GST/DRC-01/{test_label}",
            authority="GST",
            status="resolved",
            received_date=date.today() - timedelta(days=20),
            response_deadline=date.today() - timedelta(days=10),
            penalty=Decimal("500000"),
            tax_demand=Decimal("1000000"),
            legal_sections=["u/s 73(9) of CGST Act"],
            risk_tier="medium",
            status_changed_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        n2 = ComplianceNotice(
            client_id=client_id,
            notice_number=f"IT/143-2/{test_label}",
            authority="IT",
            status="under_review",
            received_date=date.today() - timedelta(days=15),
            response_deadline=date.today() + timedelta(days=15),
            penalty=Decimal("250000"),
            legal_sections=["u/s 143(2)"],
            risk_tier="high",
        )
        n3 = ComplianceNotice(
            client_id=client_id,
            notice_number=f"SEBI/ENF/{test_label}",
            authority="SEBI",
            status="received",
            received_date=date.today(),
            penalty=Decimal("2000000"),
            risk_tier="critical",
        )
        db.add_all([n1, n2, n3])
        db.flush()
        notice_ids = [n1.id, n2.id, n3.id]

        # 2 documents with extracted text
        d1 = Document(
            user_id=admin_id,
            filename="invoice_q3.pdf",
            original_filename=f"invoice_{test_label}.pdf",
            file_type="pdf",
            file_size=2048,
            file_path=f"/tmp/{test_label}_1.pdf",
            status="completed",
            extracted_text="Tax invoice issued under GST Act for goods supplied in Q3 FY2026",
        )
        d2 = Document(
            user_id=admin_id,
            filename="ledger.pdf",
            original_filename=f"ledger_{test_label}.pdf",
            file_type="pdf",
            file_size=4096,
            file_path=f"/tmp/{test_label}_2.pdf",
            status="completed",
            extracted_text="Supplier ledger showing all GST input tax credit transactions",
        )
        db.add_all([d1, d2])
        db.flush()
        doc_ids = [d1.id, d2.id]

        db.commit()

        # Backfill search_vector for documents (Phase 4 trigger should fire on
        # INSERT, but if not, force a touch). For safety:
        db.execute(text("""
            UPDATE documents SET search_vector = to_tsvector('english',
                COALESCE(extracted_text, '') || ' ' || COALESCE(original_filename, ''))
            WHERE id = ANY(:ids) AND search_vector IS NULL
        """), {"ids": doc_ids})
        db.commit()

        # Set tenant context for the read path (defence in depth — RESET ROLE
        # already bypassed RLS, but services don't know that)
        set_tenant_context_for_celery(client_id=client_id, user_id=admin_id, cross_mode=False)

        print(f"Fixture: client={client_id} notices={notice_ids} docs={doc_ids}")

        # ── Test 1: GST query should hit notice n1 + both documents owned
        # by this user (CRIT-1 hardening: documents leg is user_id-scoped)
        hits = search(db, query="GST", user_id=admin_id, entity_types=("notice", "document"))
        notice_hits = [h for h in hits if h.entity_type == "notice"]
        doc_hits = [h for h in hits if h.entity_type == "document"]
        if not notice_hits:
            failures.append("GST query: no notice hits (expected n1)")
        if len(doc_hits) < 2:
            failures.append(f"GST query: expected ≥2 doc hits, got {len(doc_hits)}")
        if len(hits) > 0 and hits[0].rank < hits[-1].rank:
            failures.append("results not ranked (highest rank first)")

        # ── Test 1b (CRIT-1 regression): search as a different user_id
        # must NOT return our smoke-fixture documents.
        other_hits = search(
            db, query="GST", user_id=admin_id + 99999, entity_types=("document",),
        )
        leaked = [h for h in other_hits if h.entity_id in doc_ids]
        if leaked:
            failures.append(
                f"CRIT-1 LEAK: search as user {admin_id + 99999} returned "
                f"smoke documents owned by {admin_id}: {[h.entity_id for h in leaked]}"
            )

        # ── Test 2: SEBI query should hit only n3 (critical)
        sebi_hits = search(db, query="SEBI", user_id=admin_id, entity_types=("notice", "document"))
        sebi_notice_hits = [h for h in sebi_hits if h.entity_type == "notice"]
        if not any(h.entity_id == n3.id for h in sebi_notice_hits):
            failures.append("SEBI query: missing n3")

        # ── Test 3: notice-only filter
        notice_only = search(db, query="GST", user_id=admin_id, entity_types=("notice",))
        if any(h.entity_type == "document" for h in notice_only):
            failures.append("entity_types=notice should not return documents")

        # ── Test 4: empty query short-circuits
        empty = search(db, query="", user_id=admin_id, entity_types=("notice", "document"))
        if empty != []:
            failures.append("empty query should return []")

        # ── Test 5: penalty_by_authority
        penalties = penalty_by_authority(db, client_id=client_id, window_days=90)
        if len(penalties) < 3:
            failures.append(f"expected ≥3 authority rows, got {len(penalties)}")
        sebi_row = next((p for p in penalties if p["authority"] == "SEBI"), None)
        if sebi_row is None:
            failures.append("penalty_by_authority missing SEBI row")
        elif sebi_row["total_penalty"] != 2000000.0:
            failures.append(f"SEBI total_penalty wrong: {sebi_row['total_penalty']}")

        # ── Test 6: notice_volume_by_status
        volumes = notice_volume_by_status(db, client_id=client_id, window_days=90)
        statuses = {v["status"]: v["count"] for v in volumes}
        if statuses.get("resolved") != 1:
            failures.append(f"resolved count wrong: {statuses.get('resolved')}")
        if statuses.get("under_review") != 1:
            failures.append(f"under_review count wrong: {statuses.get('under_review')}")
        if statuses.get("received") != 1:
            failures.append(f"received count wrong: {statuses.get('received')}")

        # ── Test 7: response_time_distribution
        rt = response_time_distribution(db, client_id=client_id, window_days=90)
        if rt["count"] != 1:
            failures.append(f"response_time count expected 1 (n1 resolved), got {rt['count']}")

        if failures:
            print("\n=== PHASE 13 SMOKE FAILED ===")
            for f in failures:
                print(f"  - {f}")
            return 1

        print("\n=== PHASE 13 SMOKE PASSED ===")
        print(f"  Unified search 'GST': {len(notice_hits)} notice + {len(doc_hits)} document hits")
        print(f"  Top rank: {hits[0].title} [{hits[0].entity_type}, {hits[0].rank:.4f}]")
        print(f"  SEBI search: {len(sebi_notice_hits)} notice hit (n3)")
        print(f"  Penalty by authority: {len(penalties)} rows")
        print(f"  Volume by status: {statuses}")
        print(f"  Response time: p50={rt['p50']:.1f}d count={rt['count']}")
        return 0

    finally:
        try:
            db.execute(text("RESET ROLE"))
            db.execute(text("SET LOCAL row_security = off"))
            if client_id is not None:
                db.execute(text("DELETE FROM compliance_notice_activity WHERE notice_id = ANY(:ids)"), {"ids": notice_ids})
                db.execute(text("DELETE FROM compliance_notices WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM compliance_client_memberships WHERE client_id = :cid"), {"cid": client_id})
                db.execute(text("DELETE FROM compliance_clients WHERE id = :cid"), {"cid": client_id})
                if doc_ids:
                    db.execute(text("DELETE FROM documents WHERE id = ANY(:ids)"), {"ids": doc_ids})
                db.commit()
                print("Cleanup OK")
        except Exception as e:
            print(f"Cleanup failed: {e}")
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
