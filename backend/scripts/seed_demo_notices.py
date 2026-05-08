"""Seed realistic Indian compliance notices for the demo tenant.

Idempotent — keyed on (client_id, notice_number). Re-running is a no-op
for already-seeded rows.

Coverage matrix:
  - All 5 notice lifecycle states: received, under_review,
    response_drafted, submitted, resolved, dismissed
  - All 5 authorities: GST, IT, MCA, RBI, SEBI
  - All 4 risk tiers: critical, high, medium, low
  - Full response approval chain: draft, reviewer_pending,
    legal_pending, cfo_pending, approved
  - NER risk-factor JSON for the WhyThisRiskScore panel
  - Activity timeline entries

Run inside the backend container:
    docker compose exec backend python /app/scripts/seed_demo_notices.py

Override the target tenant (defaults to admin's first membership):
    docker compose exec backend env DEMO_CLIENT_ID=206 DEMO_USER_ID=7 \\
        python /app/scripts/seed_demo_notices.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

# Make the app importable when this script is run as a file.
sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# Resolve target tenant + admin
# ─────────────────────────────────────────────────────────────────────


def resolve_targets(db) -> tuple[int, int]:
    """Return (client_id, user_id). Honours env overrides; otherwise
    picks the first compliance_head membership for any active admin."""
    client_id = os.environ.get("DEMO_CLIENT_ID")
    user_id = os.environ.get("DEMO_USER_ID")
    if client_id and user_id:
        return int(client_id), int(user_id)

    row = db.execute(
        text(
            """
            SELECT m.client_id, m.user_id
            FROM compliance_client_memberships m
            JOIN users u ON u.id = m.user_id
            WHERE u.role = 'admin'
              AND u.is_active = TRUE
              AND m.compliance_role = 'compliance_head'
            ORDER BY m.id ASC
            LIMIT 1
            """
        )
    ).first()
    if not row:
        raise SystemExit(
            "No active admin user with a compliance_head membership found; "
            "set DEMO_CLIENT_ID + DEMO_USER_ID env vars to override."
        )
    return row[0], row[1]


# ─────────────────────────────────────────────────────────────────────
# Notice specs
# ─────────────────────────────────────────────────────────────────────

# One day relative to today — keeps deadlines realistic regardless of
# when the seed runs.
TODAY = date.today()


def d(offset_days: int) -> date:
    return TODAY + timedelta(days=offset_days)


# Each spec: notice fields PLUS optional `response` describing the
# approval state to seed alongside the notice.
NOTICE_SPECS: list[dict] = [
    {
        "notice_number": "GST/2026/DRC-7841",
        "authority": "GST",
        "status": "received",
        "risk_tier": "high",
        "risk_score": 0.78,
        "received_date": d(-1),
        "response_deadline": d(13),
        "tax_demand": 642000,
        "interest": 41200,
        "penalty": 64200,
        "total_liability": 747400,
        "legal_sections": ["Section 73", "Rule 142(1)"],
        "ner": {
            "gstins": ["29AABCS1429F1Z6"],
            "section_references": ["Section 73", "Rule 142(1)"],
            "risk_top_factors": [
                {"feature": "GSTR-3B vs GSTR-1 mismatch", "contribution": 0.31, "phrase": "discrepancy of ₹6,42,000"},
                {"feature": "Section 73 demand", "contribution": 0.24, "phrase": "Section 73"},
                {"feature": "Reply window < 30 days", "contribution": 0.18, "phrase": "within 30 days"},
            ],
        },
    },
    {
        "notice_number": "ITBA/AST/S.148/9821",
        "authority": "IT",
        "status": "received",
        "risk_tier": "critical",
        "risk_score": 0.93,
        "received_date": d(-2),
        "response_deadline": d(28),
        "tax_demand": 4280000,
        "interest": 312500,
        "penalty": 0,
        "total_liability": 4592500,
        "legal_sections": ["Section 148", "Section 149", "Section 151"],
        "ner": {
            "pans": ["AABCS1429F"],
            "section_references": ["Section 148"],
            "risk_top_factors": [
                {"feature": "Section 148 reopening", "contribution": 0.42, "phrase": "income chargeable to tax has escaped assessment"},
                {"feature": "Liability > ₹40L", "contribution": 0.27, "phrase": "₹42,80,000"},
                {"feature": "AY 2018-19 (timely under §149)", "contribution": 0.14, "phrase": "Section 149"},
            ],
        },
    },
    {
        "notice_number": "GST/AT/2026/0042",
        "authority": "GST",
        "status": "under_review",
        "risk_tier": "medium",
        "risk_score": 0.51,
        "received_date": d(-7),
        "response_deadline": d(8),
        "tax_demand": 184000,
        "interest": 11900,
        "penalty": 18400,
        "total_liability": 214300,
        "legal_sections": ["Section 74"],
        "ner": {
            "gstins": ["29AABCS1429F1Z6"],
            "section_references": ["Section 74"],
            "risk_top_factors": [
                {"feature": "ITC mismatch with GSTR-2B", "contribution": 0.22, "phrase": "ineligible input tax credit"},
                {"feature": "Section 74 (suppression alleged)", "contribution": 0.19, "phrase": "wilful misstatement"},
            ],
        },
    },
    {
        "notice_number": "MCA/CIN/QRY/2026/115",
        "authority": "MCA",
        "status": "under_review",
        "risk_tier": "low",
        "risk_score": 0.22,
        "received_date": d(-10),
        "response_deadline": d(20),
        "tax_demand": 0,
        "interest": 0,
        "penalty": 25000,
        "total_liability": 25000,
        "legal_sections": ["Section 92", "Rule 11"],
        "ner": {
            "section_references": ["Section 92"],
            "risk_top_factors": [
                {"feature": "Annual return clarification", "contribution": 0.12, "phrase": "AOC-4 query"},
            ],
        },
    },
    # ---- response_drafted ↘ DRAFT ----
    {
        "notice_number": "GST/2026/DRC-3217",
        "authority": "GST",
        "status": "response_drafted",
        "risk_tier": "high",
        "risk_score": 0.71,
        "received_date": d(-14),
        "response_deadline": d(6),
        "tax_demand": 892000,
        "interest": 67800,
        "penalty": 89200,
        "total_liability": 1049000,
        "legal_sections": ["Section 73"],
        "ner": {"gstins": ["29AABCS1429F1Z6"], "section_references": ["Section 73"]},
        "response": {
            "status": "draft",
            "subject": "Reply to GST/2026/DRC-3217 — reconciliation pending",
            "body": (
                "Drafting reconciliation between GSTR-3B and GSTR-2B for the "
                "FY 2024-25 period. Awaiting vendor invoices for Q3 to close "
                "the ITC gap before final submission."
            ),
            "approvals_done": [],
        },
    },
    # ---- response_drafted ↘ REVIEWER_PENDING ----
    {
        "notice_number": "ITBA/AST/2026/4521",
        "authority": "IT",
        "status": "response_drafted",
        "risk_tier": "medium",
        "risk_score": 0.48,
        "received_date": d(-21),
        "response_deadline": d(4),
        "tax_demand": 312000,
        "interest": 28100,
        "penalty": 0,
        "total_liability": 340100,
        "legal_sections": ["Section 142(1)"],
        "ner": {"pans": ["AABCS1429F"], "section_references": ["Section 142(1)"]},
        "response": {
            "status": "reviewer_pending",
            "subject": "Submission under §142(1) — books of account",
            "body": (
                "Producing books of account for AY 2024-25, scope as per "
                "questionnaire dated 12-Mar-2025. Awaiting peer review before "
                "filing."
            ),
            "approvals_done": [],
        },
    },
    # ---- response_drafted ↘ LEGAL_PENDING ----
    {
        "notice_number": "RBI/FED/COMP/2026/89",
        "authority": "RBI",
        "status": "response_drafted",
        "risk_tier": "medium",
        "risk_score": 0.55,
        "received_date": d(-30),
        "response_deadline": d(11),
        "tax_demand": 0,
        "interest": 0,
        "penalty": 0,
        "total_liability": 0,
        "legal_sections": ["FEMA Section 13"],
        "ner": {"section_references": ["FEMA §13"]},
        "response": {
            "status": "legal_pending",
            "subject": "Submission under FEMA §13 — ODI compliance",
            "body": (
                "Providing supporting documents for the ODI investment "
                "tranche dated 14-Jan-2026, including form ODI-Part I and "
                "share allotment certificate. Reviewer signed off; with "
                "Legal for §13 phrasing."
            ),
            "approvals_done": ["reviewer"],
        },
    },
    # ---- response_drafted ↘ CFO_PENDING ----
    {
        "notice_number": "SEBI/HO/CFD/2026/1042",
        "authority": "SEBI",
        "status": "response_drafted",
        "risk_tier": "high",
        "risk_score": 0.74,
        "received_date": d(-25),
        "response_deadline": d(9),
        "tax_demand": 0,
        "interest": 0,
        "penalty": 1500000,
        "total_liability": 1500000,
        "legal_sections": ["Regulation 30 LODR"],
        "ner": {"section_references": ["Regulation 30 LODR"]},
        "response": {
            "status": "cfo_pending",
            "subject": "Reply to SEBI/HO/CFD/2026/1042 — Reg 30 disclosure",
            "body": (
                "Submission addresses the alleged delay in Regulation 30 "
                "disclosure of the M&A event dated 28-Feb-2026. Reviewer + "
                "Legal cleared. Pending CFO signature before filing."
            ),
            "approvals_done": ["reviewer", "legal"],
        },
    },
    # ---- submitted with full approval chain ----
    {
        "notice_number": "GST/2026/DRC-1099",
        "authority": "GST",
        "status": "submitted",
        "risk_tier": "high",
        "risk_score": 0.69,
        "received_date": d(-45),
        "response_deadline": d(-15),
        "tax_demand": 1240000,
        "interest": 89400,
        "penalty": 124000,
        "total_liability": 1453400,
        "legal_sections": ["Section 73", "Section 50"],
        "ner": {"gstins": ["29AABCS1429F1Z6"], "section_references": ["Section 73"]},
        "response": {
            "status": "approved",
            "subject": "Reply filed for GST/2026/DRC-1099",
            "body": (
                "Final reply submitted via the GST portal on 24-Apr-2026. "
                "ITC reconciliation attached, prior-period adjustments "
                "documented."
            ),
            "approvals_done": ["reviewer", "legal", "cfo"],
        },
    },
    {
        "notice_number": "ITBA/2025/0892",
        "authority": "IT",
        "status": "resolved",
        "risk_tier": "low",
        "risk_score": 0.18,
        "received_date": d(-92),
        "response_deadline": d(-60),
        "compliance_date": d(-30),
        "tax_demand": 47000,
        "interest": 5200,
        "penalty": 0,
        "total_liability": 52200,
        "legal_sections": ["Section 143(2)"],
        "ner": {"section_references": ["Section 143(2)"]},
        "response": {
            "status": "approved",
            "subject": "Reply to ITBA/2025/0892 — closed favourably",
            "body": "Routine §143(2) follow-up; clarifications accepted by AO.",
            "approvals_done": ["reviewer", "legal", "cfo"],
        },
    },
    {
        "notice_number": "MCA/2025/0712",
        "authority": "MCA",
        "status": "dismissed",
        "risk_tier": "low",
        "risk_score": 0.11,
        "received_date": d(-110),
        "response_deadline": d(-80),
        "tax_demand": 0,
        "interest": 0,
        "penalty": 5000,
        "total_liability": 5000,
        "legal_sections": [],
        "ner": {},
    },
    # ─── 18 additional notices (Wave 5: 30-notice demo) ────────────────
    # Distribution: 4 received / 3 under_review / 4 response_drafted /
    # 3 submitted / 3 resolved / 1 dismissed.
    # Deadlines fanned across [-30, +60] days so the calendar populates.
    # Risk tiers: 2 critical, 5 high, 8 medium, 3 low (combined with the
    # earlier 11 + 1 pre-existing → 30 across the four tiers).
    # ── received (4) ──
    {
        "notice_number": "GST/2026/DRC-9012",
        "authority": "GST",
        "status": "received",
        "risk_tier": "medium",
        "risk_score": 0.46,
        "received_date": d(-1),
        "response_deadline": d(15),
        "tax_demand": 218000, "interest": 14300, "penalty": 21800,
        "total_liability": 254100,
        "legal_sections": ["Section 73"],
        "ner": {"gstins": ["27AABCS1429F1Z6"], "section_references": ["Section 73"]},
    },
    {
        "notice_number": "ITBA/AST/2026/8821",
        "authority": "IT", "status": "received",
        "risk_tier": "high", "risk_score": 0.66,
        "received_date": d(-2), "response_deadline": d(22),
        "tax_demand": 1820000, "interest": 142000, "penalty": 0,
        "total_liability": 1962000,
        "legal_sections": ["Section 143(2)", "Section 143(3)"],
        "ner": {"pans": ["AABCS1429F"], "section_references": ["Section 143(2)"]},
    },
    {
        "notice_number": "SEBI/HO/2026/2103",
        "authority": "SEBI", "status": "received",
        "risk_tier": "critical", "risk_score": 0.88,
        "received_date": d(-3), "response_deadline": d(7),
        "tax_demand": 0, "interest": 0, "penalty": 5000000,
        "total_liability": 5000000,
        "legal_sections": ["Regulation 4 PIT", "Regulation 30 LODR"],
        "ner": {"section_references": ["Regulation 4 PIT"],
                "risk_top_factors": [
                    {"feature": "Insider trading allegation", "contribution": 0.40, "phrase": "Regulation 4 PIT"},
                    {"feature": "Penalty > ₹50L", "contribution": 0.28, "phrase": "₹50,00,000"},
                    {"feature": "7-day reply window", "contribution": 0.20, "phrase": "within 7 days"},
                ]},
    },
    {
        "notice_number": "MCA/CIN/2026/2204",
        "authority": "MCA", "status": "received",
        "risk_tier": "low", "risk_score": 0.19,
        "received_date": d(-1), "response_deadline": d(28),
        "tax_demand": 0, "interest": 0, "penalty": 10000,
        "total_liability": 10000,
        "legal_sections": ["Section 137"],
        "ner": {"section_references": ["Section 137"]},
    },
    # ── under_review (3) ──
    {
        "notice_number": "GST/2026/DRC-5601",
        "authority": "GST", "status": "under_review",
        "risk_tier": "high", "risk_score": 0.72,
        "received_date": d(-5), "response_deadline": d(10),
        "tax_demand": 1280000, "interest": 92000, "penalty": 128000,
        "total_liability": 1500000,
        "legal_sections": ["Section 74"],
        "ner": {"gstins": ["27AABCS1429F1Z6"], "section_references": ["Section 74"]},
    },
    {
        "notice_number": "RBI/2026/FED/142",
        "authority": "RBI", "status": "under_review",
        "risk_tier": "medium", "risk_score": 0.50,
        "received_date": d(-8), "response_deadline": d(18),
        "tax_demand": 0, "interest": 0, "penalty": 250000,
        "total_liability": 250000,
        "legal_sections": ["FEMA Section 6", "Master Direction ECB"],
        "ner": {"section_references": ["FEMA §6"]},
    },
    {
        "notice_number": "ITBA/AST/2026/9045",
        "authority": "IT", "status": "under_review",
        "risk_tier": "medium", "risk_score": 0.43,
        "received_date": d(-12), "response_deadline": d(25),
        "tax_demand": 421000, "interest": 38500, "penalty": 0,
        "total_liability": 459500,
        "legal_sections": ["Section 142(1)"],
        "ner": {"section_references": ["Section 142(1)"]},
    },
    # ── response_drafted (4) — varied approval stages, varied roles ──
    {
        "notice_number": "GST/2026/DRC-4488",
        "authority": "GST", "status": "response_drafted",
        "risk_tier": "high", "risk_score": 0.68,
        "received_date": d(-18), "response_deadline": d(5),
        "tax_demand": 982000, "interest": 71400, "penalty": 98200,
        "total_liability": 1151600,
        "legal_sections": ["Section 73"],
        "ner": {"gstins": ["27AABCS1429F1Z6"], "section_references": ["Section 73"]},
        "response": {"status": "draft",
                     "subject": "Reply to GST/2026/DRC-4488 — drafter working",
                     "body": "Initial draft pending vendor reconciliation for Q2 FY24-25.",
                     "approvals_done": []},
    },
    {
        "notice_number": "ITBA/AST/2026/3372",
        "authority": "IT", "status": "response_drafted",
        "risk_tier": "medium", "risk_score": 0.52,
        "received_date": d(-22), "response_deadline": d(3),
        "tax_demand": 268000, "interest": 24100, "penalty": 0,
        "total_liability": 292100,
        "legal_sections": ["Section 142(1)"],
        "ner": {"pans": ["AABCS1429F"], "section_references": ["Section 142(1)"]},
        "response": {"status": "reviewer_pending",
                     "subject": "§142(1) — books of account submission",
                     "body": "Submitting trial balance + ledger extracts for AY 2024-25 Q1. Awaiting reviewer sign-off.",
                     "approvals_done": []},
    },
    {
        "notice_number": "RBI/2026/FED/198",
        "authority": "RBI", "status": "response_drafted",
        "risk_tier": "medium", "risk_score": 0.49,
        "received_date": d(-28), "response_deadline": d(12),
        "tax_demand": 0, "interest": 0, "penalty": 0,
        "total_liability": 0,
        "legal_sections": ["FEMA Section 13", "Master Direction LRS"],
        "ner": {"section_references": ["FEMA §13"]},
        "response": {"status": "legal_pending",
                     "subject": "LRS clarification reply",
                     "body": "Documents for outward remittance trail attached. Reviewer cleared, with Legal for §13 phrasing.",
                     "approvals_done": ["reviewer"]},
    },
    {
        "notice_number": "SEBI/HO/CFD/2026/3081",
        "authority": "SEBI", "status": "response_drafted",
        "risk_tier": "critical", "risk_score": 0.85,
        "received_date": d(-32), "response_deadline": d(2),
        "tax_demand": 0, "interest": 0, "penalty": 7500000,
        "total_liability": 7500000,
        "legal_sections": ["Regulation 4 PIT"],
        "ner": {"section_references": ["Regulation 4 PIT"]},
        "response": {"status": "cfo_pending",
                     "subject": "Reply to SEBI/HO/CFD/2026/3081 — UPSI handling",
                     "body": "Reply addresses UPSI sharing trail per Reg 4. Reviewer + Legal cleared. Pending CFO sign-off before SEBI portal filing.",
                     "approvals_done": ["reviewer", "legal"]},
    },
    # ── submitted (3) ──
    {
        "notice_number": "GST/2026/DRC-2210",
        "authority": "GST", "status": "submitted",
        "risk_tier": "medium", "risk_score": 0.54,
        "received_date": d(-40), "response_deadline": d(-8),
        "tax_demand": 524000, "interest": 38900, "penalty": 52400,
        "total_liability": 615300,
        "legal_sections": ["Section 73"],
        "ner": {"gstins": ["27AABCS1429F1Z6"], "section_references": ["Section 73"]},
        "response": {"status": "approved",
                     "subject": "Reply filed for DRC-2210",
                     "body": "Submitted via portal 2026-04-30 with reconciliation annexures.",
                     "approvals_done": ["reviewer", "legal", "cfo"]},
    },
    {
        "notice_number": "MCA/CIN/2025/4451",
        "authority": "MCA", "status": "submitted",
        "risk_tier": "low", "risk_score": 0.21,
        "received_date": d(-50), "response_deadline": d(-20),
        "tax_demand": 0, "interest": 0, "penalty": 25000,
        "total_liability": 25000,
        "legal_sections": ["Section 92"],
        "ner": {"section_references": ["Section 92"]},
        "response": {"status": "approved",
                     "subject": "AOC-4 clarification filed",
                     "body": "Annual return amendments uploaded; awaiting MCA acceptance.",
                     "approvals_done": ["reviewer", "legal", "cfo"]},
    },
    {
        "notice_number": "ITBA/AST/2025/6612",
        "authority": "IT", "status": "submitted",
        "risk_tier": "high", "risk_score": 0.63,
        "received_date": d(-55), "response_deadline": d(-25),
        "tax_demand": 920000, "interest": 73500, "penalty": 0,
        "total_liability": 993500,
        "legal_sections": ["Section 143(3)"],
        "ner": {"pans": ["AABCS1429F"], "section_references": ["Section 143(3)"]},
        "response": {"status": "approved",
                     "subject": "Scrutiny reply — AY 2023-24",
                     "body": "Books reviewed and submitted with reconciliation memo.",
                     "approvals_done": ["reviewer", "legal", "cfo"]},
    },
    # ── resolved (3) ──
    {
        "notice_number": "GST/2025/DRC-7700",
        "authority": "GST", "status": "resolved",
        "risk_tier": "medium", "risk_score": 0.41,
        "received_date": d(-100), "response_deadline": d(-65),
        "compliance_date": d(-30),
        "tax_demand": 312000, "interest": 0, "penalty": 0,
        "total_liability": 312000,
        "legal_sections": ["Section 73"],
        "ner": {"gstins": ["27AABCS1429F1Z6"], "section_references": ["Section 73"]},
        "response": {"status": "approved",
                     "subject": "DRC-7700 — paid in full, closed",
                     "body": "Demand paid via DRC-03; matter closed favourably.",
                     "approvals_done": ["reviewer", "legal", "cfo"]},
    },
    {
        "notice_number": "RBI/2025/FED/0089",
        "authority": "RBI", "status": "resolved",
        "risk_tier": "low", "risk_score": 0.16,
        "received_date": d(-120), "response_deadline": d(-90),
        "compliance_date": d(-60),
        "tax_demand": 0, "interest": 0, "penalty": 0,
        "total_liability": 0,
        "legal_sections": ["FEMA Section 13"],
        "ner": {"section_references": ["FEMA §13"]},
        "response": {"status": "approved",
                     "subject": "ODI compliance — accepted",
                     "body": "RBI accepted explanation for delayed Form ODI filing.",
                     "approvals_done": ["reviewer", "legal", "cfo"]},
    },
    {
        "notice_number": "MCA/CIN/2025/3320",
        "authority": "MCA", "status": "resolved",
        "risk_tier": "low", "risk_score": 0.13,
        "received_date": d(-140), "response_deadline": d(-110),
        "compliance_date": d(-80),
        "tax_demand": 0, "interest": 0, "penalty": 5000,
        "total_liability": 5000,
        "legal_sections": ["Section 92"],
        "ner": {"section_references": ["Section 92"]},
        "response": {"status": "approved",
                     "subject": "MCA query closed",
                     "body": "MGT-7 filed with corrections.",
                     "approvals_done": ["reviewer", "legal", "cfo"]},
    },
    # ── dismissed (1) ──
    {
        "notice_number": "GST/2025/DRC-1188",
        "authority": "GST", "status": "dismissed",
        "risk_tier": "medium", "risk_score": 0.38,
        "received_date": d(-95), "response_deadline": d(-65),
        "tax_demand": 184000, "interest": 0, "penalty": 18400,
        "total_liability": 202400,
        "legal_sections": ["Section 74"],
        "ner": {"gstins": ["27AABCS1429F1Z6"], "section_references": ["Section 74"]},
    },
]


# ─────────────────────────────────────────────────────────────────────
# Seed
# ─────────────────────────────────────────────────────────────────────


def upsert_notice(db, client_id: int, user_id: int, spec: dict) -> tuple[int, bool]:
    """Insert one notice + optional response if not already present.
    Returns (notice_id, created_flag)."""
    existing = db.execute(
        text(
            "SELECT id FROM compliance_notices "
            "WHERE client_id = :client_id AND notice_number = :nn"
        ),
        {"client_id": client_id, "nn": spec["notice_number"]},
    ).first()
    if existing:
        return existing[0], False

    now = datetime.now(timezone.utc)
    notice_id = db.execute(
        text(
            """
            INSERT INTO compliance_notices (
                client_id, notice_number, authority, status,
                received_date, response_deadline, compliance_date,
                tax_demand, interest, penalty, total_liability,
                legal_sections, risk_score, risk_tier,
                ner_extracted_fields, model_version,
                source, status_changed_at, created_by_user_id,
                created_at, updated_at, classified_at, risk_scored_at
            ) VALUES (
                :client_id, :nn, :authority, :status,
                :received, :deadline, :compliance_date,
                :tax_demand, :interest, :penalty, :total,
                CAST(:legal_sections AS jsonb), :risk_score, :risk_tier,
                CAST(:ner AS jsonb), 'demo-seed-v1',
                'manual', :now, :user_id,
                :now, :now, :now, :now
            )
            RETURNING id
            """
        ),
        {
            "client_id": client_id,
            "nn": spec["notice_number"],
            "authority": spec["authority"],
            "status": spec["status"],
            "received": spec["received_date"],
            "deadline": spec.get("response_deadline"),
            "compliance_date": spec.get("compliance_date"),
            "tax_demand": spec.get("tax_demand"),
            "interest": spec.get("interest"),
            "penalty": spec.get("penalty"),
            "total": spec.get("total_liability"),
            "legal_sections": json.dumps(spec.get("legal_sections", [])),
            "risk_score": spec.get("risk_score"),
            "risk_tier": spec.get("risk_tier"),
            "ner": json.dumps(spec.get("ner", {})),
            "now": now,
            "user_id": user_id,
        },
    ).scalar()

    # Activity timeline — minimum 2 entries (created + status change to current).
    db.execute(
        text(
            "INSERT INTO compliance_notice_activity "
            "(notice_id, user_id, type, details, created_at) "
            "VALUES (:nid, :uid, 'note_added', "
            " CAST(:details AS jsonb), :ts)"
        ),
        {
            "nid": notice_id,
            "uid": user_id,
            "details": json.dumps({"text": "Notice intake — auto-classified", "source": "demo-seed"}),
            "ts": now - timedelta(hours=12),
        },
    )
    if spec["status"] != "received":
        db.execute(
            text(
                "INSERT INTO compliance_notice_activity "
                "(notice_id, user_id, type, details, created_at) "
                "VALUES (:nid, :uid, 'status_change', "
                " CAST(:details AS jsonb), :ts)"
            ),
            {
                "nid": notice_id,
                "uid": user_id,
                "details": json.dumps({"from": "received", "to": spec["status"]}),
                "ts": now - timedelta(hours=6),
            },
        )

    # Optional response chain.
    if "response" in spec:
        seed_response(db, client_id, user_id, notice_id, spec["response"], now)

    return notice_id, True


def seed_response(db, client_id, user_id, notice_id, rspec, now):
    """Insert notice_responses + notice_response_versions + N approvals."""
    response_id = db.execute(
        text(
            "INSERT INTO notice_responses "
            "(notice_id, client_id, status, created_by_user_id, created_at, updated_at) "
            "VALUES (:nid, :cid, :status, :uid, :now, :now) RETURNING id"
        ),
        {
            "nid": notice_id,
            "cid": client_id,
            "status": rspec["status"],
            "uid": user_id,
            "now": now,
        },
    ).scalar()

    version_id = db.execute(
        text(
            """
            INSERT INTO notice_response_versions
            (response_id, client_id, version_no, subject, body_markdown,
             created_by_user_id, created_at)
            VALUES (:rid, :cid, 1, :subj, :body, :uid, :now)
            RETURNING id
            """
        ),
        {
            "rid": response_id,
            "cid": client_id,
            "subj": rspec["subject"],
            "body": rspec["body"],
            "uid": user_id,
            "now": now,
        },
    ).scalar()

    db.execute(
        text("UPDATE notice_responses SET current_version_id = :vid WHERE id = :rid"),
        {"vid": version_id, "rid": response_id},
    )

    # Approval audit rows for stages already passed.
    for offset, stage in enumerate(rspec.get("approvals_done", [])):
        db.execute(
            text(
                """
                INSERT INTO notice_response_approvals
                (response_id, version_id, client_id, stage, decision,
                 actor_user_id, reason, created_at)
                VALUES (:rid, :vid, :cid, :stage, 'approved', :uid, :reason, :ts)
                """
            ),
            {
                "rid": response_id,
                "vid": version_id,
                "cid": client_id,
                "stage": stage,
                "uid": user_id,
                "reason": f"Demo seed: {stage} approved",
                "ts": now - timedelta(hours=(3 - offset)),
            },
        )


# ─────────────────────────────────────────────────────────────────────
# Verify state-machine invariants
# ─────────────────────────────────────────────────────────────────────


def verify_state_machine_invariants(db, client_id: int) -> list[str]:
    """Return a list of violations. Empty list = green."""
    bad = []

    # 1. Every notice in `submitted` or terminal status should have a
    #    response in `approved` (the only path to `submitted` is via
    #    APPROVED response per Phase 12).
    rows = db.execute(
        text(
            """
            SELECT n.id, n.notice_number, n.status, r.status AS rstatus
            FROM compliance_notices n
            LEFT JOIN notice_responses r ON r.notice_id = n.id
            WHERE n.client_id = :cid AND n.status IN ('submitted', 'resolved')
            """
        ),
        {"cid": client_id},
    ).fetchall()
    for nid, nn, ns, rs in rows:
        if rs != "approved":
            bad.append(f"  Notice {nn} is {ns} but response status = {rs!r} (expected 'approved')")

    # 2. Every `response_drafted` notice should have a non-terminal response.
    rows = db.execute(
        text(
            """
            SELECT n.id, n.notice_number, r.status AS rstatus
            FROM compliance_notices n
            LEFT JOIN notice_responses r ON r.notice_id = n.id
            WHERE n.client_id = :cid AND n.status = 'response_drafted'
            """
        ),
        {"cid": client_id},
    ).fetchall()
    valid_pending = {"draft", "reviewer_pending", "legal_pending", "cfo_pending"}
    for nid, nn, rs in rows:
        if rs not in valid_pending:
            bad.append(f"  Notice {nn} is response_drafted but response status = {rs!r}")

    # 3. Approvals trail must match the stage list. e.g., a response in
    #    legal_pending must have exactly 1 approval row (reviewer); cfo_pending
    #    must have 2 (reviewer + legal); approved must have 3.
    expected = {
        "draft": 0,
        "reviewer_pending": 0,
        "legal_pending": 1,
        "cfo_pending": 2,
        "approved": 3,
    }
    rows = db.execute(
        text(
            """
            SELECT r.id, r.status,
                   (SELECT count(*) FROM notice_response_approvals
                    WHERE response_id = r.id) AS approval_count
            FROM notice_responses r
            JOIN compliance_notices n ON n.id = r.notice_id
            WHERE n.client_id = :cid
            """
        ),
        {"cid": client_id},
    ).fetchall()
    for rid, rs, ac in rows:
        if rs in expected and ac != expected[rs]:
            bad.append(
                f"  Response {rid} status={rs} expected {expected[rs]} approvals, has {ac}"
            )

    return bad


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> int:
    db = SessionLocal()
    try:
        # FORCE ROW LEVEL SECURITY on compliance_* tables overrides
        # postgres-role BYPASSRLS. SET row_security = off is the
        # documented escape hatch (PG >= 9.5; needs SUPERUSER or
        # BYPASSRLS — postgres has both on Supabase). Without this,
        # the cross-table membership lookup below sees zero rows.
        db.execute(text("SET row_security = off"))
        client_id, user_id = resolve_targets(db)
        print(f"Target: client_id={client_id}, user_id={user_id}")

        created = 0
        skipped = 0
        for spec in NOTICE_SPECS:
            _, was_created = upsert_notice(db, client_id, user_id, spec)
            if was_created:
                created += 1
            else:
                skipped += 1

        db.commit()

        print(f"Seeded {created} new notice(s), skipped {skipped} existing.")
        print()

        # Summary
        rows = db.execute(
            text(
                """
                SELECT status, count(*) AS n
                FROM compliance_notices
                WHERE client_id = :cid
                GROUP BY 1 ORDER BY 1
                """
            ),
            {"cid": client_id},
        ).fetchall()
        print("Notice counts by status:")
        for status, n in rows:
            print(f"  {status:18s}  {n}")

        rows = db.execute(
            text(
                """
                SELECT r.status, count(*) AS n
                FROM notice_responses r
                JOIN compliance_notices n ON n.id = r.notice_id
                WHERE n.client_id = :cid
                GROUP BY 1 ORDER BY 1
                """
            ),
            {"cid": client_id},
        ).fetchall()
        print("Response counts by status:")
        for status, n in rows:
            print(f"  {status:18s}  {n}")

        # Invariants
        print()
        print("State-machine invariants:")
        violations = verify_state_machine_invariants(db, client_id)
        if violations:
            print("  FAIL — violations found:")
            for v in violations:
                print(v)
            return 1
        print("  OK — all seeded rows pass state-machine invariants.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
