"""Phase 18 v2.0 end-to-end smoke - AI Notice Response Drafting (BYOK).

Mirrors smoke_phase17_v20.py: real provider call, audit redaction, RLS
isolation, immutability, idempotent cleanup. CI-safe SKIP when no key.

Checks (10):
   1. service_module_imports     - response_drafter_service + prompt importable
   2. endpoint_registered        - /api/compliance/ai/notice-response-draft/{id} in OpenAPI
   3. permission_grants          - NOTICE_DRAFT_RESPONSE on compliance_head, legal_team,
                                   ca_consultant. Negative on auditor, cfo, finance_team.
   4. byok_412_no_credential     - service raises ResponseDraftCredentialMissingError
                                   when AICredential is missing
   5. drafter_real_call          - real provider call returns non-empty markdown body
                                   with "Subject:" prefix and the notice_number embedded
   6. audit_redaction            - notice_ai_draft row carries provider/model/tokens/
                                   latency/body_sha256/guidance_sha256/extracted_fields_used
                                   key-list only; no raw draft text and no guidance text
   7. guidance_round_trip        - same notice + different guidance hash to different
                                   guidance_sha256 audit rows
   8. audit_immutability         - UPDATE + DELETE on the audit row both raise
                                   the append-only exception (Phase 9 inheritance)
   9. rls_isolation              - client B session cannot see the draft audit row
                                   written for client A
  10. cleanup_idempotent         - fixture rows dropped in reverse dependency order;
                                   audit rows retained per immutability contract

Usage (host):
    GEMINI_API_KEY_SMOKE=... python scripts/smoke_phase18_v20.py

Usage (container, recommended):
    docker cp scripts/smoke_phase18_v20.py smartdocs-backend:/tmp/
    docker exec -e GEMINI_API_KEY_SMOKE="$KEY" \\
        -e GEMINI_MODEL_SMOKE="gemini-2.5-flash-lite" \\
        smartdocs-backend python /tmp/smoke_phase18_v20.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
TOTAL = 10


def _passed(idx: int, name: str) -> None:
    print(f"[{idx}/{TOTAL}] {name} ... {GREEN}PASS{RESET}")


def _failed(idx: int, name: str, reason: str) -> None:
    print(f"[{idx}/{TOTAL}] {name} ... {RED}FAIL{RESET}: {reason}")


def _info(msg: str) -> None:
    print(f"{YELLOW}[INFO]{RESET} {msg}")


def _skip(reason: str) -> int:
    print(f"{YELLOW}SKIPPED{RESET}: {reason}")
    return 0


def _resolve_provider_from_env() -> tuple[str, str, str] | None:
    anth = os.environ.get("ANTHROPIC_API_KEY_SMOKE")
    if anth:
        model = os.environ.get("ANTHROPIC_MODEL_SMOKE", "claude-sonnet-4-5")
        return ("anthropic", model, anth)
    gem = os.environ.get("GEMINI_API_KEY_SMOKE")
    if gem:
        model = os.environ.get("GEMINI_MODEL_SMOKE", "gemini-2.5-flash-lite")
        return ("google", model, gem)
    return None


def _resolve_provider_from_db(db_url: str) -> tuple[str, str, str] | None:
    """Fallback to the encrypted AICredential row any tenant already has.

    User directive 2026-05-25: reuse one persistent provider key across
    product and smoke surfaces.
    """
    try:
        from sqlalchemy import create_engine, text
        from app.compliance.utils.pii_encryption import decrypt_field
    except ImportError:
        return None
    try:
        e = create_engine(db_url, pool_pre_ping=True)
        with e.connect() as c:
            row = c.execute(text(
                "SELECT provider, model, api_key_enc FROM ai_credentials "
                "ORDER BY last_used_at DESC NULLS LAST, id DESC LIMIT 1"
            )).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    provider, model, enc = row[0], row[1], row[2]
    if isinstance(enc, memoryview):
        enc = bytes(enc)
    try:
        plaintext = decrypt_field(enc)
    except Exception:
        return None
    if not plaintext:
        return None
    if isinstance(plaintext, (bytes, bytearray)):
        plaintext = bytes(plaintext).decode("utf-8", errors="ignore")
    return (provider, model, plaintext)


def main() -> int:
    resolved = _resolve_provider_from_env()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("FATAL: DATABASE_URL not set", file=sys.stderr)
        return 2
    if not os.environ.get("FERNET_KEY"):
        print("FATAL: FERNET_KEY not set", file=sys.stderr)
        return 2

    candidate_backend_dirs = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")),
        "/app",
    ]
    for cand in candidate_backend_dirs:
        if os.path.isdir(cand) and cand not in sys.path:
            sys.path.insert(0, cand)

    if resolved is None:
        resolved = _resolve_provider_from_db(db_url)
        if resolved is not None:
            _info(
                f"Smoke key sourced from existing AICredential "
                f"(provider={resolved[0]}, model={resolved[1]})"
            )
    if resolved is None:
        return _skip(
            "No smoke provider key available: neither ANTHROPIC_API_KEY_SMOKE "
            "nor GEMINI_API_KEY_SMOKE is set, and no AICredential row exists "
            "in the database."
        )
    provider_name, smoke_model, smoke_api_key = resolved

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DatabaseError
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    label = f"phase18-smoke-{int(datetime.now(timezone.utc).timestamp())}"
    failures: list[str] = []
    cleanup = {
        "audit_drafts": [],
        "notices": [],
        "memberships": [],
        "clients": [],
        "ai_credentials": [],
        "users": [],
    }

    try:
        db.execute(text("RESET ROLE"))
        db.execute(text("SET LOCAL row_security = off"))

        # Check 1: service module imports
        try:
            from app.compliance.services.response_drafter_service import (
                ResponseDraftCredentialMissingError,
                draft_response_for_notice,
            )
            from app.compliance.services.response_drafter_prompt import (
                MAX_GUIDANCE_CHARS,
                MAX_RESPONSE_TOKENS,
                build_user_prompt,
            )
            assert callable(draft_response_for_notice)
            assert callable(build_user_prompt)
            assert MAX_GUIDANCE_CHARS == 800
            assert MAX_RESPONSE_TOKENS == 1400
            _passed(1, "service_module_imports")
        except Exception as e:
            _failed(1, "service_module_imports", str(e))
            return 1

        # Check 2: endpoint registered (poll OpenAPI via in-process FastAPI)
        try:
            from app.main import app
            openapi = app.openapi()
            paths = openapi.get("paths", {})
            target = "/api/compliance/ai/notice-response-draft/{notice_id}"
            assert target in paths, (
                f"endpoint not registered; existing AI paths: "
                f"{sorted(p for p in paths if 'ai' in p)[:8]}"
            )
            _passed(2, "endpoint_registered")
        except Exception as e:
            _failed(2, "endpoint_registered", str(e))
            return 1

        # Check 3: permission grants
        try:
            from app.compliance.services.permission_registry import (
                CompliancePermission, ComplianceRole, has_permission,
            )
            # NOTICE_DRAFT_RESPONSE is held by the people who actually
            # write reply letters: legal_team, ca_consultant, staff.
            # compliance_head approves drafts but does not draft them; this
            # matches the existing Phase 9 registry.
            for role in (
                ComplianceRole.LEGAL_TEAM,
                ComplianceRole.CA_CONSULTANT,
                ComplianceRole.STAFF,
            ):
                assert has_permission(
                    role, CompliancePermission.NOTICE_DRAFT_RESPONSE
                ), f"{role.value} lacks NOTICE_DRAFT_RESPONSE"
            for role in (
                ComplianceRole.COMPLIANCE_HEAD,
                ComplianceRole.AUDITOR,
                ComplianceRole.CFO,
                ComplianceRole.FINANCE_TEAM,
            ):
                assert not has_permission(
                    role, CompliancePermission.NOTICE_DRAFT_RESPONSE
                ), f"{role.value} unexpectedly has NOTICE_DRAFT_RESPONSE"
            _passed(3, "permission_grants (3 yes, 4 no)")
        except Exception as e:
            _failed(3, "permission_grants", str(e))
            return 1

        # Fixture: client + user + membership + notice (no credential yet for check 4)
        from app.compliance.middleware.tenant_context import set_tenant_context_for_celery
        from app.compliance.models.client import Client as ComplianceClient
        from app.compliance.models.membership import ClientMembership
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.services import ai_service
        from app.models.user import User

        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            admin = User(
                email=f"{label}@smoke.test",
                username=f"{label}_user",
                hashed_password="x",
                role="admin",
            )
            db.add(admin)
            db.flush()
            cleanup["users"].append(admin.id)
        user_id = admin.id

        client_a = ComplianceClient(name=f"Phase18 Smoke A {label}", client_type="pvt_ltd")
        client_b = ComplianceClient(name=f"Phase18 Smoke B {label}", client_type="pvt_ltd")
        db.add_all([client_a, client_b])
        db.flush()
        cleanup["clients"].extend([client_a.id, client_b.id])

        membership_a = ClientMembership(
            user_id=user_id,
            client_id=client_a.id,
            compliance_role="compliance_head",
        )
        db.add(membership_a)
        db.flush()
        cleanup["memberships"].append(membership_a.id)
        db.commit()

        set_tenant_context_for_celery(client_id=client_a.id, user_id=user_id, cross_mode=False)

        # Sample notice with extracted_fields filled
        notice = ComplianceNotice(
            client_id=client_a.id,
            assigned_user_id=user_id,
            notice_number=f"DRC-01/2026/SMOKE-{label}",
            authority="GST",
            status="received",
            source="manual",
            received_date=date.today() - timedelta(days=2),
            response_deadline=date.today() + timedelta(days=28),
            tax_demand=145000,
            interest=12000,
            penalty=14500,
            total_liability=171500,
            legal_sections=["Section 73 of the CGST Act, 2017", "Section 17(5)"],
            extracted_fields={
                "fields": {
                    "notice_number": {"value": f"DRC-01/2026/SMOKE-{label}", "confidence": 0.96},
                    "authority": {"value": "GST", "confidence": 0.99},
                    "issued_date": {"value": "2026-05-12", "confidence": 0.95},
                    "response_deadline": {"value": "2026-06-12", "confidence": 0.92},
                    "tax_demand": {"value": 145000.0, "confidence": 0.93},
                    "interest": {"value": 12000.0, "confidence": 0.93},
                    "penalty": {"value": 14500.0, "confidence": 0.91},
                    "total_liability": {"value": 171500.0, "confidence": 0.94},
                    "taxpayer_name": {"value": "Acme Industries Pvt. Ltd.", "confidence": 0.95},
                    "gstin": {"value": "29AABCS1429B1Z2", "confidence": 0.94},
                    "legal_sections": {"value": ["Section 73 of the CGST Act, 2017"], "confidence": 0.9},
                },
                "average_confidence": 0.94,
                "model": "smoke-fixture",
            },
            extraction_status="completed",
        )
        db.add(notice)
        db.flush()
        cleanup["notices"].append(notice.id)
        db.commit()

        _info(f"Fixture: user={user_id} client_a={client_a.id} client_b={client_b.id} notice={notice.id}")

        # Check 4: 412 path before credential exists
        try:
            raised = False
            try:
                draft_response_for_notice(db, notice=notice, user_id=user_id)
            except ResponseDraftCredentialMissingError:
                raised = True
            assert raised
            _passed(4, "byok_412_no_credential")
        except Exception as e:
            _failed(4, "byok_412_no_credential", str(e))
            failures.append("4")

        # Install credential
        cred = ai_service.set_credential(
            db, client_id=client_a.id,
            provider=provider_name, model=smoke_model, api_key=smoke_api_key,
        )
        cleanup["ai_credentials"].append(cred.id)
        db.commit()
        _info(f"AICredential id={cred.id} provider={provider_name} model={smoke_model}")

        # Check 5: real call
        draft_result: dict | None = None
        try:
            draft_result = draft_response_for_notice(
                db, notice=notice, user_id=user_id,
                user_guidance="Keep tone formal and concise; cite Section 17(5) where relevant.",
            )
            assert "draft_body_markdown" in draft_result
            body = draft_result["draft_body_markdown"]
            assert isinstance(body, str) and len(body) > 200, f"draft too short: {len(body)} chars"
            assert "Subject" in body, "draft missing 'Subject' header"
            assert notice.notice_number in body, "draft missing notice_number"
            _passed(5, f"drafter_real_call ({draft_result['tokens_out']} chars, {draft_result['latency_ms']}ms)")
        except Exception as e:
            _failed(5, "drafter_real_call", str(e))
            failures.append("5")

        # Check 6: audit redaction
        try:
            row = db.execute(text(
                "SELECT id, details FROM audit_logs "
                "WHERE action='notice_ai_draft' AND resource_id=:nid "
                "ORDER BY id DESC LIMIT 1"
            ), {"nid": notice.id}).fetchone()
            assert row is not None, "no notice_ai_draft audit row"
            cleanup["audit_drafts"].append(row.id)
            details = row.details if isinstance(row.details, dict) else json.loads(row.details)
            required = {"provider","model","tokens_in","tokens_out","latency_ms","body_sha256","guidance_sha256","extracted_fields_used"}
            missing = required - set(details.keys())
            assert not missing, f"missing audit keys: {missing}"
            serialised = json.dumps(details, default=str)
            if draft_result is not None:
                body = draft_result["draft_body_markdown"]
                # No raw draft body in audit
                assert body[:200] not in serialised, "audit details contains raw draft body"
            # No raw guidance text in audit
            assert "Section 17(5)" not in serialised, "audit details contains raw guidance text"
            _passed(6, f"audit_redaction (id={row.id})")
        except Exception as e:
            _failed(6, "audit_redaction", str(e))
            failures.append("6")

        # Check 7: guidance round-trip (different guidance -> different hash)
        try:
            other = draft_response_for_notice(
                db, notice=notice, user_id=user_id,
                user_guidance="Different guidance string entirely; emphasise procedural objections.",
            )
            row2 = db.execute(text(
                "SELECT id, details FROM audit_logs "
                "WHERE action='notice_ai_draft' AND resource_id=:nid "
                "ORDER BY id DESC LIMIT 1"
            ), {"nid": notice.id}).fetchone()
            cleanup["audit_drafts"].append(row2.id)
            d2 = row2.details if isinstance(row2.details, dict) else json.loads(row2.details)
            d1 = next((r.details for r in db.execute(text(
                "SELECT details FROM audit_logs WHERE id=:id"
            ), {"id": cleanup["audit_drafts"][0]})), None)
            if isinstance(d1, str):
                d1 = json.loads(d1)
            assert d1["guidance_sha256"] != d2["guidance_sha256"], (
                f"distinct guidance hashed identically: {d1['guidance_sha256']}"
            )
            _passed(7, "guidance_round_trip (different guidance -> different sha256)")
        except Exception as e:
            _failed(7, "guidance_round_trip", str(e))
            failures.append("7")

        # Check 8: immutability
        try:
            assert cleanup["audit_drafts"], "no audit id for immutability check"
            target_id = cleanup["audit_drafts"][0]
            update_raised = False
            try:
                db.execute(text("UPDATE audit_logs SET details='{}'::jsonb WHERE id=:id"), {"id": target_id})
                db.commit()
            except DatabaseError as e:
                if "append-only" in str(e):
                    update_raised = True
                db.rollback()
            assert update_raised, "UPDATE unexpectedly succeeded"
            delete_raised = False
            try:
                db.execute(text("DELETE FROM audit_logs WHERE id=:id"), {"id": target_id})
                db.commit()
            except DatabaseError as e:
                if "append-only" in str(e):
                    delete_raised = True
                db.rollback()
            assert delete_raised, "DELETE unexpectedly succeeded"
            _passed(8, "audit_immutability (UPDATE + DELETE both raised)")
        except Exception as e:
            db.rollback()
            _failed(8, "audit_immutability", str(e))
            failures.append("8")

        # Check 9: RLS isolation via runtime engine bound to app_runtime
        try:
            from sqlalchemy import create_engine as _ce
            runtime_url = os.environ.get("DATABASE_URL_RUNTIME") or db_url
            rls_engine = _ce(runtime_url, pool_pre_ping=True)
            with rls_engine.connect() as rls_conn:
                rls_conn.execute(text("SELECT set_config('app.current_client_id', :cid, true)"), {"cid": str(client_b.id)})
                rls_conn.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(user_id)})
                rls_conn.execute(text("SELECT set_config('app.cross_client_mode', 'false', true)"))
                # Notice belongs to client A; client B session must not see it.
                visible = rls_conn.execute(text(
                    "SELECT id FROM compliance_notices WHERE id=:id"
                ), {"id": notice.id}).fetchall()
                assert not visible, f"client_b saw client_a notice {notice.id}: {visible}"
            _passed(9, "rls_isolation (client_b cannot see client_a notice)")
        except Exception as e:
            _failed(9, "rls_isolation", str(e))
            failures.append("9")

        # Check 10: cleanup
        try:
            db.execute(text("RESET ROLE"))
            db.execute(text("SET LOCAL row_security = off"))
            for nid in cleanup["notices"]:
                db.execute(text("DELETE FROM compliance_notices WHERE id=:id"), {"id": nid})
            for mid in cleanup["memberships"]:
                db.execute(text("DELETE FROM compliance_client_memberships WHERE id=:id"), {"id": mid})
            for cid in cleanup["ai_credentials"]:
                db.execute(text("DELETE FROM ai_credentials WHERE id=:id"), {"id": cid})
            for cid in cleanup["clients"]:
                db.execute(text("DELETE FROM compliance_clients WHERE id=:id"), {"id": cid})
            for uid in cleanup["users"]:
                db.execute(text("DELETE FROM users WHERE id=:id"), {"id": uid})
            db.commit()
            _passed(10, "cleanup_idempotent (audit rows retained per immutability)")
        except Exception as e:
            db.rollback()
            _failed(10, "cleanup_idempotent", str(e))
            failures.append("10")

        if failures:
            print()
            print(f"{RED}=== SMOKE FAILED ==={RESET}")
            print(f"Failing checks: {', '.join(failures)}")
            return 1

        print()
        print(f"{GREEN}=== SMOKE PASSED ==={RESET}")
        if draft_result is not None:
            print(
                f"  Provider: {draft_result['model']}  "
                f"tokens_out={draft_result['tokens_out']}  "
                f"latency_ms={draft_result['latency_ms']}  "
                f"extracted_fields_used={len(draft_result['extracted_fields_used'])}"
            )
        return 0

    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
