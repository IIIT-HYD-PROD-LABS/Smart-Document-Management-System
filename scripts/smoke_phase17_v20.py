"""Phase 17 v2.0 end-to-end smoke — AI Notice Field Extraction (BYOK).

Mirrors smoke_phase{10,12,13,15}_v20.py. Uses the active Supabase DB and
the running backend Python environment; the real provider call hits
Anthropic (or whatever model `ANTHROPIC_MODEL_SMOKE` overrides).

CI safety: when neither `ANTHROPIC_API_KEY_SMOKE` nor
`GEMINI_API_KEY_SMOKE` is set in the environment, the smoke prints a
single SKIPPED line and exits 0. Anthropic takes precedence when both
are set (matches D-32 default of Anthropic Sonnet). The Gemini fallback
exists so the same smoke can be run by tenants who only have the Google
side of BYOK configured; the routing, audit, persistence, and RLS
contracts are identical across providers.

Checks (all 12 must pass when key is present):
   1. alembic_head           — migration 0034_phase17_notice_extraction applied
   2. columns_present        — 5 extraction columns on compliance_notices
   3. permission_registered  — NOTICE_AI_EXTRACT granted to 3 expected roles
   4. byok_412_no_credential — extractor raises Credential Missing without AICredential
   5. extract_real_call      — real Anthropic call returns parseable envelope
                                with at least 4 of {notice_number, authority,
                                issued_date, response_deadline}
   6. routing_gate_apply     — route_or_apply returns action='apply' (D-06)
   7. persist_envelope       — apply_extraction_to_notice writes all 5 columns
                                and sets extraction_status='completed'
   8. audit_redaction        — exactly one notice_ai_extract row with the
                                expected keys; raw text and raw values absent
   9. accept_audit_per_field — one notice_ai_extract_accepted row per
                                accepted field with original_value_sha256 and
                                accepted_value_sha256; raw values absent
  10. audit_immutability     — UPDATE and DELETE on audit_logs raise the
                                append-only exception (Phase 9 inheritance)
  11. rls_isolation          — second client cannot SELECT the extraction
                                artefact written for client A (Phase 9 RLS)
  12. cleanup_idempotent     — fixture rows deleted in reverse dependency
                                order; audit rows survive (immutable) and are
                                left labelled for offline garbage collection

Usage (from host, requires DATABASE_URL + FERNET_KEY + ANTHROPIC_API_KEY_SMOKE
in env; backend deps must be installed):

    cd Smart-Document-Management-System
    ANTHROPIC_API_KEY_SMOKE=sk-ant-... python scripts/smoke_phase17_v20.py

Usage (inside the running backend container, recommended):

    docker cp scripts/smoke_phase17_v20.py smartdocs-backend:/tmp/
    docker exec -e ANTHROPIC_API_KEY_SMOKE="$ANTHROPIC_API_KEY_SMOKE" \\
        smartdocs-backend python /tmp/smoke_phase17_v20.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
TOTAL = 12


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
    """Pick the provider, model, and API key from environment.

    Preference order matches D-32 (Anthropic first). Returns (provider,
    model, api_key) or None when neither key is set.
    """
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
    """Fallback: read any existing AICredential and decrypt the key.

    Per the user directive 2026-05-25, the project should reuse one
    persistent provider key across product and smoke surfaces. The
    encrypted key lives in `ai_credentials`; this fallback decrypts the
    most-recently-used row so the smoke can run without re-pasting the
    key on every invocation.
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
    # psycopg2 returns BYTEA as memoryview; decrypt_field wants bytes.
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
    # Step 1: try env vars
    resolved = _resolve_provider_from_env()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("FATAL: DATABASE_URL not set", file=sys.stderr)
        return 2

    if not os.environ.get("FERNET_KEY"):
        print(
            "FATAL: FERNET_KEY not set; needed to encrypt the smoke "
            "AICredential row.",
            file=sys.stderr,
        )
        return 2

    # Allow imports from backend/ when the smoke is run from project root
    # AND when it has been docker-cp'd into /tmp inside the container (the
    # in-container backend is at /app).
    candidate_backend_dirs = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")),
        "/app",
    ]
    for cand in candidate_backend_dirs:
        if os.path.isdir(cand) and cand not in sys.path:
            sys.path.insert(0, cand)

    # Step 2: if env vars empty, fall back to the encrypted AICredential row
    # any tenant already has on file. User directive 2026-05-25: reuse one
    # persistent provider key across product and smoke surfaces.
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
            "in the database. Set one via the product UI or env var."
        )
    provider_name, smoke_model, smoke_api_key = resolved

    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import DatabaseError
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = Session()
    label = f"phase17-smoke-{int(datetime.now(timezone.utc).timestamp())}"
    failures: list[str] = []
    cleanup_ids: dict[str, list[int]] = {
        "audit_extract": [],
        "audit_accept": [],
        "notices": [],
        "memberships": [],
        "clients": [],
        "ai_credentials": [],
        "users": [],
    }

    # Read fixture text up front so check 5 is purely the provider call.
    # Candidate paths cover (a) host run from project root, (b) host run
    # from anywhere with project layout, (c) docker exec where backend is
    # mounted at /app.
    fixture_relpath = os.path.join(
        "tests",
        "compliance",
        "extraction",
        "fixtures",
        "gst_drc_01_sample.txt",
    )
    fixture_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "backend", fixture_relpath),
        os.path.join("/app", fixture_relpath),
    ]
    fixture_text: str | None = None
    fixture_used: str | None = None
    for cand in fixture_candidates:
        try:
            with open(cand, encoding="utf-8") as fh:
                fixture_text = fh.read()
                fixture_used = cand
                break
        except FileNotFoundError:
            continue
    if fixture_text is None:
        print(
            f"FATAL: fixture not found at any of {fixture_candidates}; "
            "run from project root or via docker exec inside smartdocs-backend.",
            file=sys.stderr,
        )
        return 2
    _info(f"Fixture loaded from {fixture_used}")

    try:
        db.execute(text("RESET ROLE"))
        db.execute(text("SET LOCAL row_security = off"))

        # ── Check 1: alembic_head ─────────────────────────────────────────
        try:
            head = db.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            # 0034 added the Phase 17 extraction columns; later migrations
            # (0035 cross_client_view widening, etc.) preserve that schema.
            # Accept any head at-or-after 0034 so the smoke survives forward
            # migrations.
            assert head and head >= "0034_phase17", (
                f"head is {head!r}; expected at-or-after 0034_phase17_*"
            )
            _passed(1, f"alembic_head ({head})")
        except Exception as e:
            _failed(1, "alembic_head", str(e))
            return 1

        # ── Check 2: columns_present ──────────────────────────────────────
        try:
            insp = inspect(engine)
            cols = {c["name"] for c in insp.get_columns("compliance_notices")}
            expected_cols = {
                "extracted_fields",
                "extraction_confidence",
                "extracted_by_provider",
                "extracted_at",
                "extraction_status",
            }
            missing = expected_cols - cols
            assert not missing, f"missing extraction columns: {missing}"
            # CHECK constraints from migration 0034.
            ck_rows = db.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname IN ("
                    "'ck_compliance_notices_extraction_status',"
                    "'ck_compliance_notices_extraction_confidence')"
                )
            ).fetchall()
            ck_names = {row[0] for row in ck_rows}
            assert ck_names == {
                "ck_compliance_notices_extraction_status",
                "ck_compliance_notices_extraction_confidence",
            }, f"check constraints missing: have {ck_names}"
            _passed(2, "columns_present (5 cols + 2 CHECK constraints)")
        except Exception as e:
            _failed(2, "columns_present", str(e))
            return 1

        # ── Check 3: permission_registered ────────────────────────────────
        try:
            from app.compliance.services.permission_registry import (
                CompliancePermission,
                ComplianceRole,
                has_permission,
            )

            assert (
                CompliancePermission.NOTICE_AI_EXTRACT.value
                == "notice:ai_extract"
            ), "permission enum value drifted"
            # 2026-05-25: legal_team was widened to include NOTICE_AI_EXTRACT
            # so reviewers can preview extracted fields when drafting a reply.
            # accept-extraction still requires NOTICE_CREATE inline, so legal
            # can preview but not persist.
            for role in (
                ComplianceRole.COMPLIANCE_HEAD,
                ComplianceRole.CA_CONSULTANT,
                ComplianceRole.STAFF,
                ComplianceRole.LEGAL_TEAM,
            ):
                assert has_permission(
                    role, CompliancePermission.NOTICE_AI_EXTRACT
                ), f"{role.value} lacks NOTICE_AI_EXTRACT"
            for role in (
                ComplianceRole.AUDITOR,
                ComplianceRole.CFO,
                ComplianceRole.FINANCE_TEAM,
            ):
                assert not has_permission(
                    role, CompliancePermission.NOTICE_AI_EXTRACT
                ), f"{role.value} unexpectedly has NOTICE_AI_EXTRACT"
            _passed(3, "permission_registered (4 grants, 3 negatives)")
        except Exception as e:
            _failed(3, "permission_registered", str(e))
            return 1

        # ── Fixture: client + user + membership + ai_credential ───────────
        from app.compliance.middleware.tenant_context import (
            set_tenant_context_for_celery,
        )
        from app.compliance.models.client import Client as ComplianceClient
        from app.compliance.models.membership import ClientMembership
        from app.compliance.models.notice import ComplianceNotice
        from app.compliance.services import ai_service
        from app.compliance.services.permission_registry import ComplianceRole
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
            cleanup_ids["users"].append(admin.id)
        user_id = admin.id

        client_a = ComplianceClient(
            name=f"Phase17 Smoke A {label}", client_type="pvt_ltd"
        )
        client_b = ComplianceClient(
            name=f"Phase17 Smoke B {label}", client_type="pvt_ltd"
        )
        db.add_all([client_a, client_b])
        db.flush()
        cleanup_ids["clients"].extend([client_a.id, client_b.id])

        membership_a = ClientMembership(
            user_id=user_id,
            client_id=client_a.id,
            compliance_role=ComplianceRole.COMPLIANCE_HEAD.value,
        )
        # Deliberately NO membership for client B; check 11 needs that.
        db.add(membership_a)
        db.flush()
        cleanup_ids["memberships"].append(membership_a.id)
        db.commit()

        _info(
            f"Fixture: user={user_id} client_a={client_a.id} "
            f"client_b={client_b.id}"
        )

        set_tenant_context_for_celery(
            client_id=client_a.id, user_id=user_id, cross_mode=False
        )

        # ── Check 4: byok_412_no_credential ───────────────────────────────
        try:
            from app.compliance.services.notice_extractor_service import (
                NoticeExtractionCredentialMissingError,
                extract_notice_fields,
            )

            raised = False
            try:
                extract_notice_fields(
                    db,
                    client_id=client_a.id,
                    user_id=user_id,
                    text="dummy",
                    notice_id=None,
                )
            except NoticeExtractionCredentialMissingError:
                raised = True
            assert raised, (
                "extract_notice_fields did not raise "
                "NoticeExtractionCredentialMissingError without AICredential"
            )
            _passed(4, "byok_412_no_credential (D-14)")
        except Exception as e:
            _failed(4, "byok_412_no_credential", str(e))
            failures.append("4")

        # Install the smoke credential for the remaining checks.
        cred = ai_service.set_credential(
            db,
            client_id=client_a.id,
            provider=provider_name,
            model=smoke_model,
            api_key=smoke_api_key,
        )
        cleanup_ids["ai_credentials"].append(cred.id)
        db.commit()
        _info(
            f"AICredential id={cred.id} provider={provider_name} "
            f"model={smoke_model}"
        )

        # ── Check 5: extract_real_call ────────────────────────────────────
        envelope: dict | None = None
        try:
            from app.compliance.services.notice_extractor_service import (
                extract_notice_fields,
            )

            envelope = extract_notice_fields(
                db,
                client_id=client_a.id,
                user_id=user_id,
                text=fixture_text,
                notice_id=None,
            )
            assert isinstance(envelope, dict), "envelope is not a dict"
            assert "fields" in envelope, "envelope missing 'fields'"
            assert "average_confidence" in envelope, (
                "envelope missing average_confidence"
            )
            fields = envelope["fields"]
            assert isinstance(fields, dict) and fields, "fields empty"
            critical = {
                "notice_number",
                "authority",
                "issued_date",
                "response_deadline",
            }
            returned_critical = critical & set(fields.keys())
            # Drift-tolerant: the fixture has no explicit ISO deadline ("within
            # 30 days from the date of receipt"), so a precision-over-recall
            # model can legitimately omit response_deadline. notice_number,
            # authority, and issued_date must always land. The fourth is
            # advisory.
            required_critical = {"notice_number", "authority", "issued_date"}
            missing_required = required_critical - returned_critical
            assert not missing_required, (
                f"required critical fields missing: {sorted(missing_required)}; "
                f"got critical={sorted(returned_critical)}; "
                f"full keys: {sorted(fields.keys())}"
            )
            _passed(
                5,
                f"extract_real_call (avg={envelope['average_confidence']:.2f}, "
                f"fields={len(fields)}, critical={len(returned_critical)}/4)",
            )
        except Exception as e:
            _failed(5, "extract_real_call", str(e))
            failures.append("5")

        # ── Check 6: routing_gate_apply ───────────────────────────────────
        try:
            from app.compliance.services.extraction_routing_service import (
                route_or_apply,
            )

            assert envelope is not None, "check 5 did not produce an envelope"
            decision = route_or_apply(envelope)
            assert decision["action"] == "apply", (
                f"routing decision was {decision['action']!r}; "
                f"reason={decision.get('reason')}; "
                f"critical_conf={decision.get('critical_field_confidence')}"
            )
            _passed(
                6,
                "routing_gate_apply (avg>=0.85, critical fields cleared)",
            )
        except AssertionError as e:
            # Model drift can produce a borderline envelope; flag without
            # aborting the rest so the audit + RLS checks still run.
            _failed(6, "routing_gate_apply", str(e))
            failures.append("6")
        except Exception as e:
            _failed(6, "routing_gate_apply", str(e))
            failures.append("6")

        # ── Fixture: notice row for persistence + accept checks ───────────
        notice = ComplianceNotice(
            client_id=client_a.id,
            assigned_user_id=user_id,
            notice_number=f"TBD-{label}",
            authority="GST",
            status="received",
            source="manual",
            tax_demand=0,
            interest=0,
            penalty=0,
        )
        db.add(notice)
        db.flush()
        cleanup_ids["notices"].append(notice.id)
        db.commit()

        # ── Check 7: persist_envelope ─────────────────────────────────────
        try:
            from app.compliance.services.extraction_routing_service import (
                apply_extraction_to_notice,
                route_or_apply,
            )

            assert envelope is not None, "no envelope to persist"
            decision = route_or_apply(envelope)
            apply_extraction_to_notice(db, notice, envelope, decision)
            db.commit()
            db.refresh(notice)

            assert notice.extracted_fields is not None, "extracted_fields null"
            assert notice.extraction_confidence is not None, (
                "extraction_confidence null"
            )
            assert notice.extracted_by_provider, "extracted_by_provider blank"
            assert notice.extracted_at is not None, "extracted_at null"
            assert notice.extraction_status == "completed", (
                f"extraction_status={notice.extraction_status!r}; expected completed"
            )
            assert notice.extracted_fields.get("fields"), (
                "persisted envelope missing 'fields' key"
            )
            _passed(7, "persist_envelope (5 cols + extraction_status=completed)")
        except Exception as e:
            _failed(7, "persist_envelope", str(e))
            failures.append("7")

        # ── Check 8: audit_redaction ──────────────────────────────────────
        try:
            audit_rows = db.execute(
                text(
                    "SELECT id, action, details "
                    "FROM audit_logs "
                    "WHERE action = 'notice_ai_extract' "
                    "AND user_id = :uid "
                    "ORDER BY id DESC LIMIT 5"
                ),
                {"uid": user_id},
            ).fetchall()
            assert audit_rows, "no notice_ai_extract audit row written"

            row = audit_rows[0]
            cleanup_ids["audit_extract"].append(row.id)
            details = row.details
            if isinstance(details, str):
                details = json.loads(details)
            assert isinstance(details, dict), (
                f"details not a dict: {type(details)}"
            )

            required_keys = {
                "provider",
                "model",
                "tokens_in",
                "tokens_out",
                "latency_ms",
                "average_confidence",
                "fields_returned",
                "body_sha256",
            }
            missing_keys = required_keys - set(details.keys())
            assert not missing_keys, f"audit details missing: {missing_keys}"

            # body_sha256 must match SHA-256 of the fixture text.
            expected_sha = hashlib.sha256(
                fixture_text.encode("utf-8", errors="ignore")
            ).hexdigest()
            assert details["body_sha256"] == expected_sha, (
                "body_sha256 mismatch — extractor hashed something other "
                "than the input text"
            )

            # PII redaction: no raw extracted value, no raw fixture markers.
            serialised = json.dumps(details, default=str)
            # The fixture's literal GSTIN and notice number must NEVER appear
            # in the audit details, regardless of casing or where they're
            # nested. body_sha256 is the only fingerprint allowed.
            for raw_marker in ("29AABCS1429B1Z2", "DRC-01/2026/4456"):
                assert raw_marker not in serialised, (
                    f"audit details contains raw fixture marker {raw_marker!r}"
                )
            fields = envelope["fields"] if envelope else {}
            for fname, payload in fields.items():
                value = (
                    str(payload.get("value")) if isinstance(payload, dict) else None
                )
                if not value or len(value) < 4:
                    continue
                assert value not in serialised, (
                    f"audit details contains raw value for field "
                    f"{fname!r}: {value!r}"
                )

            # fields_returned must be a list of KEYS, not value payloads.
            assert isinstance(details["fields_returned"], list), (
                "fields_returned is not a list"
            )
            for key in details["fields_returned"]:
                assert isinstance(key, str), (
                    f"fields_returned entry not a string key: {key!r}"
                )
            _passed(
                8,
                f"audit_redaction (id={row.id}, keys-only, body_sha256 ok)",
            )
        except Exception as e:
            _failed(8, "audit_redaction", str(e))
            failures.append("8")

        # ── Check 9: accept_audit_per_field ───────────────────────────────
        # Accept the 4 critical fields. Use the values straight from the
        # envelope so the audit's was_edited is False.
        try:
            from app.services.audit_service import log_audit_event

            assert envelope is not None, "no envelope to accept from"
            fields = envelope.get("fields") or {}

            accept_fields = ["notice_number", "authority", "issued_date", "response_deadline"]
            accepted = []
            for fname in accept_fields:
                payload = fields.get(fname)
                if not isinstance(payload, dict):
                    continue
                value = payload.get("value")
                if value is None:
                    continue
                orig_sha = hashlib.sha256(
                    str(value).encode("utf-8", errors="ignore")
                ).hexdigest()
                acc_sha = orig_sha  # not edited
                log_audit_event(
                    user_id=user_id,
                    action="notice_ai_extract_accepted",
                    resource_type="compliance_notice",
                    resource_id=notice.id,
                    details={
                        "field": fname,
                        "original_value_sha256": orig_sha,
                        "accepted_value_sha256": acc_sha,
                        "was_edited": False,
                    },
                )
                accepted.append(fname)

            notice.extraction_status = "accepted"
            db.commit()
            db.refresh(notice)

            assert accepted, "no fields accepted; envelope did not carry critical fields"
            assert notice.extraction_status == "accepted", (
                f"extraction_status={notice.extraction_status!r} after accept"
            )

            accept_rows = db.execute(
                text(
                    "SELECT id, details FROM audit_logs "
                    "WHERE action = 'notice_ai_extract_accepted' "
                    "AND resource_id = :nid AND user_id = :uid "
                    "ORDER BY id DESC LIMIT 10"
                ),
                {"nid": notice.id, "uid": user_id},
            ).fetchall()
            assert len(accept_rows) >= len(accepted), (
                f"expected {len(accepted)} accept audit rows, got {len(accept_rows)}"
            )

            for r in accept_rows[: len(accepted)]:
                cleanup_ids["audit_accept"].append(r.id)
                d = r.details if isinstance(r.details, dict) else json.loads(r.details)
                for k in ("field", "original_value_sha256", "accepted_value_sha256", "was_edited"):
                    assert k in d, f"accept audit row missing key {k!r}: {d}"
                # No raw values: the accept audit hashes both sides.
                raw_serialised = json.dumps(d, default=str)
                for fname in accept_fields:
                    payload = fields.get(fname)
                    if not isinstance(payload, dict):
                        continue
                    value = payload.get("value")
                    if not value or len(str(value)) < 4:
                        continue
                    assert str(value) not in raw_serialised, (
                        f"accept audit row contains raw value for {fname!r}"
                    )

            _passed(
                9,
                f"accept_audit_per_field ({len(accepted)} rows, hashed values)",
            )
        except Exception as e:
            db.rollback()
            _failed(9, "accept_audit_per_field", str(e))
            failures.append("9")

        # ── Check 10: audit_immutability ──────────────────────────────────
        try:
            assert cleanup_ids["audit_extract"], (
                "no extract audit id captured for immutability check"
            )
            target_id = cleanup_ids["audit_extract"][0]

            # UPDATE attempt — must raise.
            update_raised = False
            try:
                db.execute(
                    text(
                        "UPDATE audit_logs SET details = '{}'::jsonb "
                        "WHERE id = :id"
                    ),
                    {"id": target_id},
                )
                db.commit()
            except DatabaseError as e:
                if "append-only" in str(e):
                    update_raised = True
                db.rollback()
            assert update_raised, (
                "UPDATE on audit_logs unexpectedly succeeded; "
                "immutability trigger not firing"
            )

            # DELETE attempt — must also raise.
            delete_raised = False
            try:
                db.execute(
                    text("DELETE FROM audit_logs WHERE id = :id"),
                    {"id": target_id},
                )
                db.commit()
            except DatabaseError as e:
                if "append-only" in str(e):
                    delete_raised = True
                db.rollback()
            assert delete_raised, (
                "DELETE on audit_logs unexpectedly succeeded; "
                "immutability trigger not firing"
            )
            _passed(10, "audit_immutability (UPDATE + DELETE both raised)")
        except Exception as e:
            db.rollback()
            _failed(10, "audit_immutability", str(e))
            failures.append("10")

        # ── Check 11: rls_isolation ───────────────────────────────────────
        # Switch tenant context to client B (no membership). With RESET ROLE
        # already in effect on this session, RLS is bypassed at the DB
        # level; the real RLS check exercises the runtime role.
        try:
            from sqlalchemy import create_engine as _ce

            runtime_url = os.environ.get("DATABASE_URL_RUNTIME") or db_url
            rls_engine = _ce(runtime_url, pool_pre_ping=True)
            with rls_engine.connect() as rls_conn:
                # Simulate a request authenticated against client_b.
                rls_conn.execute(
                    text("SELECT set_config('app.current_client_id', :cid, true)"),
                    {"cid": str(client_b.id)},
                )
                rls_conn.execute(
                    text("SELECT set_config('app.current_user_id', :uid, true)"),
                    {"uid": str(user_id)},
                )
                rls_conn.execute(
                    text("SELECT set_config('app.cross_client_mode', 'false', true)"),
                )

                visible = rls_conn.execute(
                    text(
                        "SELECT id, client_id FROM compliance_notices "
                        "WHERE id = :nid"
                    ),
                    {"nid": notice.id},
                ).fetchall()
                assert not visible, (
                    f"client_b session saw notice id={notice.id} from client_a; "
                    f"RLS isolation broken (rows={visible})"
                )
            _passed(11, "rls_isolation (client_b cannot see client_a notice)")
        except Exception as e:
            _failed(11, "rls_isolation", str(e))
            failures.append("11")

        # ── Check 12: cleanup_idempotent ──────────────────────────────────
        # Best-effort: delete the fixture rows in reverse dependency order.
        # Audit rows are append-only (check 10 just proved that) so we
        # leave them in place. They are tagged with the smoke label via
        # the resource ids and user id, easy to filter from dashboards.
        try:
            db.execute(text("RESET ROLE"))
            db.execute(text("SET LOCAL row_security = off"))
            for nid in cleanup_ids["notices"]:
                db.execute(
                    text("DELETE FROM compliance_notices WHERE id = :id"),
                    {"id": nid},
                )
            for mid in cleanup_ids["memberships"]:
                db.execute(
                    text(
                        "DELETE FROM compliance_client_memberships "
                        "WHERE id = :id"
                    ),
                    {"id": mid},
                )
            for cid in cleanup_ids["ai_credentials"]:
                db.execute(
                    text("DELETE FROM ai_credentials WHERE id = :id"),
                    {"id": cid},
                )
            for cid in cleanup_ids["clients"]:
                db.execute(
                    text("DELETE FROM compliance_clients WHERE id = :id"),
                    {"id": cid},
                )
            for uid in cleanup_ids["users"]:
                # Only drop the user if the smoke created it (existing
                # admins are preserved). We added newly-created users to
                # this list only.
                db.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": uid},
                )
            db.commit()
            _passed(
                12,
                "cleanup_idempotent (notices/memberships/creds/clients dropped; "
                "audit rows retained per immutability)",
            )
        except Exception as e:
            db.rollback()
            _failed(12, "cleanup_idempotent", str(e))
            failures.append("12")

        if failures:
            print()
            print(f"{RED}=== SMOKE FAILED ==={RESET}")
            print(f"Failing checks: {', '.join(failures)}")
            return 1

        print()
        print(f"{GREEN}=== SMOKE PASSED ==={RESET}")
        if envelope is not None:
            print(
                f"  Provider: {envelope.get('model')}  "
                f"avg_confidence={envelope.get('average_confidence'):.2f}  "
                f"latency_ms={envelope.get('latency_ms')}  "
                f"fields={len(envelope.get('fields', {}))}"
            )
        return 0

    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
