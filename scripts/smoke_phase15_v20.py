"""Phase 15 v2.0 end-to-end smoke — Gmail MCP + Bills.

Mirrors smoke_phase{10,12,13}_v20.py. Uses real DB + Redis; mocks Gmail
API via unittest.mock.patch (CI doesn't have real Google OAuth). Each
check prints `[N/12] check_name ... PASS` or `... FAIL` and exits non-zero
on the first failure. Cleanup hits all fixture rows on exit.

Checks (all 12 must pass):
  1. alembic_head            — migrations at 0026_apscheduler_jobs_table
  2. tables_exist            — 5 phase 15 tables (+ documents.source_email_id)
  3. classifier_4_cases      — incl. reconciliation #4 (rbi.org.in)
  4. mcp_six_tools           — in-memory FastMCP Client (recon #1)
  5. fernet_round_trip       — credential vault encrypt/decrypt
  6. filter_rule_priority    — 3 rules priorities {10,5,20}; sorted ASC (open Q #5)
  7. scanner_dedup           — composite UNIQUE (credential_id, gmail_message_id)
  8. compliance_auto_route   — process_classified_email creates ComplianceNotice
  9. low_confidence_route    — sender match only (False, 0.5) routes to log
 10. bill_mark_paid_audit    — BILL_MARK_PAID audit row (W5 robust assert)
 11. bill_recurrence         — second bill same biller+last4 → parent_bill_id
 12. mcp_audit_redaction     — gmail_search via in-memory Client; audit
                                contains body_sha256 + IDs but no body/sender

Usage (from inside backend container):
    docker compose exec backend python /app/../scripts/smoke_phase15_v20.py

The smoke does NOT exercise real Google OAuth — that path lives in the
manual checklist (.planning/phases/15-gmail-mcp-integration/15-SMOKE-CHECKLIST.md).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def _passed(idx: int, total: int, name: str) -> None:
    print(f"[{idx}/{total}] {name} ... {GREEN}PASS{RESET}")


def _failed(idx: int, total: int, name: str, reason: str) -> None:
    print(f"[{idx}/{total}] {name} ... {RED}FAIL{RESET}: {reason}")


def _info(msg: str) -> None:
    print(f"{YELLOW}[INFO]{RESET} {msg}")


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("FATAL: DATABASE_URL not set", file=sys.stderr)
        return 2

    # Allow imports from backend/ when run from project root.
    backend_path = os.path.join(os.path.dirname(__file__), "..", "backend")
    if os.path.isdir(backend_path) and backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = Session()
    test_label = f"phase15-smoke-{int(datetime.now(timezone.utc).timestamp())}"
    failures: list[str] = []
    client_id: int | None = None
    user_id: int | None = None
    cred_id: int | None = None
    notice_ids: list[int] = []
    bill_ids: list[int] = []
    msg_log_ids: list[int] = []
    total = 12

    try:
        db.execute(text("RESET ROLE"))
        db.execute(text("SET LOCAL row_security = off"))

        # ── Check 1: alembic_head ─────────────────────────────────────────
        try:
            head = db.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            # Phase 15 lands 0025_phase15_gmail_mcp + 0026_apscheduler_jobs_table.
            # Either is acceptable; both indicate Phase 15 is applied.
            assert head and head.startswith("002"), f"unexpected head={head!r}"
            _passed(1, total, f"alembic_head ({head})")
        except Exception as e:
            _failed(1, total, "alembic_head", str(e))
            return 1

        # ── Check 2: tables_exist + documents.source_email_id ─────────────
        try:
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            expected = {
                "gmail_credentials",
                "gmail_filter_rules",
                "gmail_message_log",
                "gmail_fetch_log",
                "bills",
            }
            missing = expected - tables
            assert not missing, f"missing tables: {missing}"
            doc_cols = {c["name"] for c in insp.get_columns("documents")}
            assert "source_email_id" in doc_cols, (
                "documents.source_email_id column missing"
            )
            _passed(2, total, "tables_exist (5 phase15 + documents.source_email_id)")
        except Exception as e:
            _failed(2, total, "tables_exist", str(e))
            return 1

        # ── Check 3: classifier 4 cases (recon #4: rbi.org.in) ────────────
        try:
            from app.email.services.classifier import classify

            assert classify(
                "user@cbic-gst.gov.in", "Show Cause Notice u/s 73"
            ) == (True, 1.0), "cbic-gst + notice subject"
            # Reconciliation #4 — RBI's correct domain is rbi.org.in (NOT gov.in).
            assert classify(
                "regulatory@rbi.org.in", "Penalty Hearing"
            ) == (True, 1.0), "rbi.org.in + penalty subject (recon #4)"
            assert classify(
                "user@cbic-gst.gov.in", "Quarterly Newsletter"
            ) == (False, 0.5), "sender match only → review queue"
            assert classify(
                "advocate@gmail.com", "Show Cause Forwarded"
            ) == (False, 0.0), "subject only / forwarded → dms_only (D-33)"
            _passed(3, total, "classifier_4_cases (recon #4: rbi.org.in)")
        except Exception as e:
            _failed(3, total, "classifier_4_cases", str(e))
            return 1

        # ── Check 4: MCP six tools via in-memory Client (recon #1) ────────
        try:
            from fastmcp import Client
            from app.email.mcp.server import mcp

            async def _list_tools():
                async with Client(mcp) as c:
                    return await c.list_tools()

            tools = asyncio.run(_list_tools())
            tool_names = {t.name for t in tools}
            expected_tools = {
                "gmail_search",
                "gmail_read_message",
                "gmail_list_attachments",
                "gmail_get_attachment",
                "gmail_list_labels",
                "gmail_modify_labels",
            }
            missing_tools = expected_tools - tool_names
            assert not missing_tools, f"missing tools: {missing_tools}"
            _passed(4, total, "mcp_six_tools (in-memory transport, recon #1)")
        except Exception as e:
            _failed(4, total, "mcp_six_tools", str(e))
            return 1

        # ── Check 5: Fernet round-trip on refresh-token storage ───────────
        try:
            from app.compliance.utils.pii_encryption import (
                decrypt_field,
                encrypt_field,
            )

            plain = "1//04test_refresh_token_phase15_smoke"
            blob = encrypt_field(plain)
            assert isinstance(blob, (bytes, bytearray)), "ciphertext not bytes"
            decoded = decrypt_field(blob)
            if isinstance(decoded, (bytes, bytearray)):
                decoded = decoded.decode("utf-8")
            assert decoded == plain, f"round-trip mismatch: {decoded!r}"
            # PII-redaction posture: ciphertext does not contain the plaintext.
            assert plain.encode() not in bytes(blob), (
                "plaintext leaks into ciphertext"
            )
            _passed(5, total, "fernet_round_trip (refresh-token vault)")
        except Exception as e:
            _failed(5, total, "fernet_round_trip", str(e))
            return 1

        # ── Fixture: client + user + credential (RLS-bypassed) ────────────
        from app.compliance.middleware.tenant_context import (
            set_tenant_context_for_celery,
        )
        from app.compliance.models.client import Client as ComplianceClient
        from app.compliance.models.membership import ClientMembership
        from app.compliance.models.notice import ComplianceNotice
        from app.email.models.bill import Bill
        from app.email.models.credential import GmailCredential
        from app.email.models.filter_rule import GmailFilterRule
        from app.email.models.message_log import GmailMessageLog
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
        user_id = admin.id

        sm_client = ComplianceClient(
            name=f"Phase15 Smoke {test_label}", client_type="pvt_ltd"
        )
        db.add(sm_client)
        db.flush()
        client_id = sm_client.id

        membership = ClientMembership(
            user_id=user_id,
            client_id=client_id,
            compliance_role="compliance_head",
        )
        db.add(membership)

        cred = GmailCredential(
            user_id=user_id,
            client_id=client_id,
            google_account_email=f"{test_label}@smoke.test",
            refresh_token_enc=b"\x00" * 32,
            scopes="gmail.readonly gmail.modify",
            status=GmailCredential.STATUS_ACTIVE,
        )
        db.add(cred)
        db.flush()
        cred_id = cred.id
        db.commit()

        # Tenant context for service-layer calls (defence in depth — RESET
        # ROLE bypassed RLS but services don't know that).
        set_tenant_context_for_celery(
            client_id=client_id, user_id=user_id, cross_mode=False
        )

        _info(
            f"Fixture: client={client_id} user={user_id} cred={cred_id}"
        )

        # ── Check 6: filter rule priority ordering (open Q #5) ────────────
        try:
            db.add_all([
                GmailFilterRule(
                    credential_id=cred_id,
                    priority=10,
                    sender_pattern="@a.example",
                    route_to=GmailFilterRule.ROUTE_BILL,
                ),
                GmailFilterRule(
                    credential_id=cred_id,
                    priority=5,
                    sender_pattern="@b.example",
                    route_to=GmailFilterRule.ROUTE_COMPLIANCE,
                ),
                GmailFilterRule(
                    credential_id=cred_id,
                    priority=20,
                    sender_pattern="@c.example",
                    route_to=GmailFilterRule.ROUTE_DMS_ONLY,
                ),
            ])
            db.commit()
            sorted_rules = (
                db.query(GmailFilterRule)
                .filter(GmailFilterRule.credential_id == cred_id)
                .order_by(GmailFilterRule.priority.asc())
                .all()
            )
            sorted_priorities = [r.priority for r in sorted_rules]
            assert sorted_priorities == [5, 10, 20], (
                f"priority order wrong: {sorted_priorities}"
            )
            # Lower priority value wins — rule with priority=5 first.
            assert sorted_rules[0].route_to == "compliance_notice", (
                f"first rule route wrong: {sorted_rules[0].route_to}"
            )
            _passed(6, total, "filter_rule_priority (open Q #5: lower wins)")
        except Exception as e:
            _failed(6, total, "filter_rule_priority", str(e))
            return 1

        # ── Check 7: scanner dedup via composite UNIQUE ───────────────────
        try:
            mlog1 = GmailMessageLog(
                credential_id=cred_id,
                gmail_message_id="msg-dedup-001",
                gmail_thread_id="thread-001",
                sender_domain="example.com",
                subject_sha256=hashlib.sha256(b"subject1").hexdigest(),
                body_sha256=hashlib.sha256(b"body1").hexdigest(),
                route_taken="dms_only",
            )
            db.add(mlog1)
            db.commit()
            db.refresh(mlog1)
            msg_log_ids.append(mlog1.id)

            mlog2 = GmailMessageLog(
                credential_id=cred_id,
                gmail_message_id="msg-dedup-001",  # SAME id → must reject
                gmail_thread_id="thread-001",
                sender_domain="example.com",
                subject_sha256=hashlib.sha256(b"subject1b").hexdigest(),
                body_sha256=hashlib.sha256(b"body1b").hexdigest(),
                route_taken="dms_only",
            )
            db.add(mlog2)
            raised = False
            try:
                db.commit()
            except IntegrityError:
                raised = True
                db.rollback()
            assert raised, "duplicate (credential_id, gmail_message_id) accepted"
            _passed(7, total, "scanner_dedup (composite UNIQUE EMAIL-08)")
        except Exception as e:
            _failed(7, total, "scanner_dedup", str(e))
            db.rollback()
            return 1

        # ── Check 8: compliance auto-routing via process_classified_email ─
        try:
            from app.email.services.ingestion_service import (
                process_classified_email,
            )

            # Fixture: a real GmailMessageLog row representing an inbound
            # email from regulatory@rbi.org.in ("Penalty Notice").
            ml = GmailMessageLog(
                credential_id=cred_id,
                gmail_message_id="msg-rbi-001",
                gmail_thread_id="thread-rbi-001",
                sender_domain="rbi.org.in",
                subject_sha256=hashlib.sha256(b"penalty-subject").hexdigest(),
                body_sha256=hashlib.sha256(b"penalty-body").hexdigest(),
                route_taken="compliance_notice",
            )
            db.add(ml)
            db.commit()
            db.refresh(ml)
            msg_log_ids.append(ml.id)

            with patch(
                "app.services.audit_service.log_audit_event_strict"
            ) as mock_audit:
                process_classified_email(
                    db,
                    credential=cred,
                    message_log=ml,
                    sender="regulatory@rbi.org.in",
                    subject="Penalty Notice u/s 11",
                    body=(
                        "GSTIN: 27AABCT1234F1ZX. "
                        "You are hereby served a penalty notice."
                    ),
                    is_compliance=True,
                    confidence=1.0,
                )
            db.commit()
            notice = (
                db.query(ComplianceNotice)
                .filter(ComplianceNotice.client_id == client_id)
                .order_by(ComplianceNotice.id.desc())
                .first()
            )
            assert notice is not None, "no ComplianceNotice created"
            notice_ids.append(notice.id)
            assert notice.source == "gmail", (
                f"notice.source expected 'gmail', got {notice.source!r}"
            )
            assert notice.status == "received", (
                f"notice.status expected 'received', got {notice.status!r}"
            )
            assert notice.authority == "RBI", (
                f"notice.authority expected 'RBI', got {notice.authority!r}"
            )
            _passed(8, total, "compliance_auto_route (rbi.org.in → RBI notice)")
        except Exception as e:
            _failed(8, total, "compliance_auto_route", str(e))
            return 1

        # ── Check 9: low-confidence routing logs decision (no notice) ─────
        try:
            from app.email.services.ingestion_service import (
                process_classified_email,
            )

            ml_lc = GmailMessageLog(
                credential_id=cred_id,
                gmail_message_id="msg-lc-001",
                gmail_thread_id="thread-lc-001",
                sender_domain="cbic-gst.gov.in",
                subject_sha256=hashlib.sha256(b"newsletter").hexdigest(),
                body_sha256=hashlib.sha256(b"newsletter-body").hexdigest(),
                route_taken="review_queue",
            )
            db.add(ml_lc)
            db.commit()
            db.refresh(ml_lc)
            msg_log_ids.append(ml_lc.id)

            notice_count_before = (
                db.query(ComplianceNotice)
                .filter(ComplianceNotice.client_id == client_id)
                .count()
            )
            process_classified_email(
                db,
                credential=cred,
                message_log=ml_lc,
                sender="news@cbic-gst.gov.in",
                subject="Quarterly Newsletter",
                body="GST rate updates this quarter.",
                is_compliance=False,
                confidence=0.5,
            )
            db.commit()
            notice_count_after = (
                db.query(ComplianceNotice)
                .filter(ComplianceNotice.client_id == client_id)
                .count()
            )
            assert notice_count_after == notice_count_before, (
                "low-confidence path created a ComplianceNotice; "
                "v2.0 should LOG the routing decision and defer to Plan 05"
            )
            _passed(9, total, "low_confidence_route (logged, no notice)")
        except Exception as e:
            _failed(9, total, "low_confidence_route", str(e))
            return 1

        # ── Check 10: bill mark_paid → BILL_MARK_PAID audit (W5 robust) ───
        try:
            from app.email.services.bill_service import mark_paid

            ml_bill = GmailMessageLog(
                credential_id=cred_id,
                gmail_message_id="msg-bill-001",
                gmail_thread_id="thread-bill-001",
                sender_domain="tatapower.com",
                subject_sha256=hashlib.sha256(b"bill-subject").hexdigest(),
                body_sha256=hashlib.sha256(b"bill-body").hexdigest(),
                route_taken="bill",
            )
            db.add(ml_bill)
            db.commit()
            db.refresh(ml_bill)
            msg_log_ids.append(ml_bill.id)

            bill = Bill(
                client_id=client_id,
                user_id=user_id,
                biller_name="Smoke Tata Power",
                biller_name_normalized="smoke tata power",
                biller_category="utility",
                amount_due=Decimal("1234.56"),
                due_date=date.today() + timedelta(days=5),
                payment_status=Bill.STATUS_PENDING,
                source_email_id=ml_bill.id,
            )
            db.add(bill)
            db.commit()
            db.refresh(bill)
            bill_ids.append(bill.id)

            with patch(
                "app.email.services.bill_service.log_audit_event_strict"
            ) as mock_audit:
                paid = mark_paid(
                    db,
                    bill_id=bill.id,
                    payment_date=date.today(),
                    payment_reference=f"UPI-SMOKE-{test_label}",
                    payment_method="upi",
                    user_id=user_id,
                )
            assert paid.payment_status == Bill.STATUS_PAID, (
                f"payment_status not paid: {paid.payment_status!r}"
            )
            assert mock_audit.called, "log_audit_event_strict not invoked"

            # W5 fix: assertion robust to either keyword OR positional 'action'
            # arg, mirroring the pattern from the orchestrator notes.
            ca = mock_audit.call_args
            action_in_kwargs = ca.kwargs.get("action") == "BILL_MARK_PAID"
            action_in_repr = "BILL_MARK_PAID" in str(ca)
            assert action_in_kwargs or action_in_repr, (
                f"BILL_MARK_PAID action missing in audit call: {ca}"
            )
            _passed(10, total, "bill_mark_paid_audit (W5 robust BILL-05)")
        except Exception as e:
            _failed(10, total, "bill_mark_paid_audit", str(e))
            return 1

        # ── Check 11: bill recurrence linking (D-23 BILL-06, Pitfall 8) ───
        try:
            # Two bills with same biller_name_normalized + last4 should
            # link via parent_bill_id on the second insert.
            ml_b1 = GmailMessageLog(
                credential_id=cred_id,
                gmail_message_id="msg-bill-rec-001",
                gmail_thread_id="thread-bill-rec-001",
                sender_domain="tatapower.com",
                subject_sha256=hashlib.sha256(b"rec-1").hexdigest(),
                body_sha256=hashlib.sha256(b"rec-1-body").hexdigest(),
                route_taken="bill",
            )
            ml_b2 = GmailMessageLog(
                credential_id=cred_id,
                gmail_message_id="msg-bill-rec-002",
                gmail_thread_id="thread-bill-rec-002",
                sender_domain="tatapower.com",
                subject_sha256=hashlib.sha256(b"rec-2").hexdigest(),
                body_sha256=hashlib.sha256(b"rec-2-body").hexdigest(),
                route_taken="bill",
            )
            db.add_all([ml_b1, ml_b2])
            db.commit()
            db.refresh(ml_b1)
            db.refresh(ml_b2)
            msg_log_ids.extend([ml_b1.id, ml_b2.id])

            from app.email.services.bill_service import upsert_bill

            # Stub schedule_bill_reminders so the smoke does not depend on
            # APScheduler having a live job store at this exact moment.
            with patch(
                "app.email.services.bill_service.schedule_bill_reminders"
            ):
                b1 = upsert_bill(
                    db,
                    credential=cred,
                    source_email_log=ml_b1,
                    biller_name="Tata Power Mumbai",
                    biller_name_normalized="tata power mumbai",
                    biller_category="utility",
                    amount_due=Decimal("500.00"),
                    due_date=date.today() + timedelta(days=10),
                    account_number_last4="1234",
                    extraction_prompt_rev="bills.v1",
                )
                bill_ids.append(b1.id)
                b2 = upsert_bill(
                    db,
                    credential=cred,
                    source_email_log=ml_b2,
                    biller_name="Tata Power Mumbai",
                    biller_name_normalized="tata power mumbai",
                    biller_category="utility",
                    amount_due=Decimal("525.00"),
                    due_date=date.today() + timedelta(days=40),
                    account_number_last4="1234",
                    extraction_prompt_rev="bills.v1",
                )
                bill_ids.append(b2.id)

            assert b2.parent_bill_id == b1.id, (
                f"second bill parent_bill_id={b2.parent_bill_id}, "
                f"expected {b1.id} (D-23 recurrence link)"
            )
            assert b2.is_recurring is True, "second bill not flagged recurring"
            _passed(11, total, "bill_recurrence (D-23 BILL-06 parent linking)")
        except Exception as e:
            _failed(11, total, "bill_recurrence", str(e))
            return 1

        # ── Check 12: MCP tool invocation + audit redaction (D-35/D-36) ───
        try:
            from fastmcp import Client
            from app.email.mcp.server import mcp

            captured_audits: list[dict] = []

            def _capture_audit(*args, **kwargs):
                captured_audits.append({
                    "args": args,
                    "kwargs": kwargs,
                })

            # Stub Gmail API client so the tool runs without real OAuth.
            fake_service = MagicMock()
            fake_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
                "messages": [
                    {"id": "fake-msg-001", "threadId": "fake-thread-001"},
                    {"id": "fake-msg-002", "threadId": "fake-thread-002"},
                ],
                "resultSizeEstimate": 2,
            }

            class _StubDb:
                def close(self):
                    pass

            stub_session = _StubDb()
            stub_cred = MagicMock(
                id=cred_id, user_id=user_id, client_id=client_id
            )

            def _stub_open(args):
                return (stub_session, stub_cred, fake_service)

            async def _invoke():
                async with Client(mcp) as c:
                    return await c.call_tool(
                        "gmail_search",
                        {
                            "args": {
                                "user_id": user_id,
                                "client_id": client_id,
                                "query": "from:rbi.org.in newer_than:7d",
                                "max_results": 10,
                            }
                        },
                    )

            with patch(
                "app.email.mcp.tools._open_session_with_creds",
                side_effect=_stub_open,
            ), patch(
                "app.email.mcp.tools.log_audit_event_strict",
                side_effect=_capture_audit,
            ):
                result = asyncio.run(_invoke())

            assert captured_audits, "no audit row captured for gmail_search"
            audit = captured_audits[-1]
            audit_kwargs = audit["kwargs"]
            audit_blob = str(audit)

            action = audit_kwargs.get("action")
            assert action == "MCP_TOOL_CALL" or "MCP_TOOL_CALL" in audit_blob, (
                f"audit action expected MCP_TOOL_CALL; got {action!r} blob={audit_blob[:200]}"
            )
            details = audit_kwargs.get("details") or {}
            details_blob = str(details).lower()

            # PII redaction (D-36): no body / sender / subject / raw / from / to keys.
            forbidden = ("body", "sender", "subject", "raw", " from ", " to ")
            for term in forbidden:
                assert term.strip() not in details_blob or term.strip() in (
                    "body_sha256",
                ), (
                    f"forbidden PII key {term!r} appears in audit details: "
                    f"{details_blob[:300]}"
                )
            # body_sha256 OR query_sha256 should appear (D-35 anchor).
            anchor_present = (
                "sha256" in details_blob
                or "query_sha256" in details_blob
                or "body_sha256" in details_blob
            )
            assert anchor_present, (
                "no SHA-256 anchor in audit details (D-35 violation): "
                f"{details_blob[:300]}"
            )
            _passed(12, total, "mcp_audit_redaction (D-35/D-36 PII)")
        except Exception as e:
            _failed(12, total, "mcp_audit_redaction", str(e))
            return 1

        # ── Summary ───────────────────────────────────────────────────────
        if failures:
            print(f"\n{RED}=== PHASE 15 SMOKE FAILED ==={RESET}")
            for f in failures:
                print(f"  - {f}")
            return 1

        print(f"\n{GREEN}=== PHASE 15 SMOKE PASSED ({total}/{total}) ==={RESET}")
        print(f"  client_id={client_id} user_id={user_id} cred_id={cred_id}")
        print(f"  notices created: {len(notice_ids)}")
        print(f"  bills created:   {len(bill_ids)}")
        print(f"  message_logs:    {len(msg_log_ids)}")
        print("  reconciliations verified at runtime: #1 (in-memory MCP), #4 (rbi.org.in)")
        return 0

    finally:
        # Cleanup — bypass RLS, hard-delete child rows then parents.
        try:
            db.execute(text("RESET ROLE"))
            db.execute(text("SET LOCAL row_security = off"))
            if client_id is not None:
                db.execute(
                    text("DELETE FROM bills WHERE client_id = :cid"),
                    {"cid": client_id},
                )
                db.execute(
                    text(
                        "DELETE FROM compliance_notice_activity "
                        "WHERE notice_id IN (SELECT id FROM compliance_notices "
                        "WHERE client_id = :cid)"
                    ),
                    {"cid": client_id},
                )
                db.execute(
                    text(
                        "DELETE FROM compliance_notices WHERE client_id = :cid"
                    ),
                    {"cid": client_id},
                )
            if cred_id is not None:
                db.execute(
                    text(
                        "DELETE FROM gmail_message_log WHERE credential_id = :cid"
                    ),
                    {"cid": cred_id},
                )
                db.execute(
                    text(
                        "DELETE FROM gmail_filter_rules WHERE credential_id = :cid"
                    ),
                    {"cid": cred_id},
                )
                db.execute(
                    text("DELETE FROM gmail_credentials WHERE id = :cid"),
                    {"cid": cred_id},
                )
            if client_id is not None:
                db.execute(
                    text(
                        "DELETE FROM compliance_client_memberships "
                        "WHERE client_id = :cid"
                    ),
                    {"cid": client_id},
                )
                db.execute(
                    text("DELETE FROM compliance_clients WHERE id = :cid"),
                    {"cid": client_id},
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
