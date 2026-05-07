"""Bill metadata extraction — BILL-01, BILL-02.

LLM-first via app.services.llm_service.extract_with_llm; regex fallback
for amount + date when LLM is unavailable. Reuses v1.0 5-provider chain.

EXTRACTION_PROMPT_REV is persisted on bills.extraction_prompt_rev so a
prompt-template revision can be rolled out without re-extracting historic
bills.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT_REV = "1.0.0"

AMOUNT_REGEX = re.compile(
    r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
ACCOUNT_REGEX = re.compile(
    r"\baccount\s*(?:number|no\.?|#)?\s*[:\-]?\s*([A-Za-z0-9]{4,20})\b",
    re.IGNORECASE,
)

BILLER_CATEGORY_HEURISTICS = [
    (
        re.compile(
            r"tatapower|adanielectricity|reliancepower|electricity|bescom|kseb|tneb|gail|igl|mahanagargas",
            re.IGNORECASE,
        ),
        "utility",
    ),
    (
        re.compile(
            r"airtel|jio|vodafone|vi\.in|bsnl|act\.fibernet|hathway",
            re.IGNORECASE,
        ),
        "telecom",
    ),
    (
        re.compile(
            r"hdfcbank|icicibank|sbicard|axisbank|kotak|amex|americanexpress|onecard",
            re.IGNORECASE,
        ),
        "credit_card",
    ),
    (
        re.compile(
            r"netflix|primevideo|hotstar|youtube|spotify|appletv|disney",
            re.IGNORECASE,
        ),
        "subscription",
    ),
]


def normalize_biller_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"\b(ltd|limited|private|pvt|inc|incorporated|llc)\b\.?", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _infer_category(sender_domain: str, biller_name: str) -> str:
    text = f"{sender_domain} {biller_name}"
    for pattern, category in BILLER_CATEGORY_HEURISTICS:
        if pattern.search(text):
            return category
    return "other"


def _regex_fallback(
    body: str,
) -> tuple[Optional[Decimal], Optional[date], Optional[str]]:
    amount: Optional[Decimal] = None
    m = AMOUNT_REGEX.search(body)
    if m:
        try:
            amount = Decimal(m.group(1).replace(",", ""))
        except InvalidOperation:
            amount = None

    due_date: Optional[date] = None
    try:
        import dateparser  # type: ignore
        for line in body.split("\n"):
            if "due" in line.lower():
                parsed = dateparser.parse(line, settings={"DATE_ORDER": "DMY"})
                if parsed:
                    due_date = parsed.date()
                    break
    except ImportError:
        pass

    account: Optional[str] = None
    am = ACCOUNT_REGEX.search(body)
    if am:
        account = am.group(1)[-4:]
    return amount, due_date, account


def extract_bill(body_text: str, sender_domain: str) -> dict:
    biller: Optional[str] = None
    amount_str = None
    due = None
    account = None
    try:
        from app.services.llm_service import extract_with_llm

        result = extract_with_llm(body_text, "bills")
        fields = result.get("fields", {}) if isinstance(result, dict) else {}

        def _val(key: str):
            v = fields.get(key)
            if isinstance(v, dict):
                return v.get("value")
            return v

        biller = _val("vendor")
        amount_str = _val("total_amount")
        due = _val("due_date")
        account = _val("account_number")
    except Exception as e:
        logger.warning("LLM extract_with_llm failed; using regex fallback: %s", e)

    amount: Optional[Decimal] = None
    if amount_str:
        try:
            amount = Decimal(str(amount_str).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            amount = None

    due_date: Optional[date] = None
    if due:
        try:
            due_date = (
                datetime.fromisoformat(str(due)).date() if isinstance(due, str) else due
            )
        except (ValueError, TypeError):
            due_date = None

    account_last4 = str(account)[-4:] if account else None

    if amount is None or due_date is None or account_last4 is None:
        r_amount, r_due, r_account = _regex_fallback(body_text)
        amount = amount or r_amount
        due_date = due_date or r_due
        account_last4 = account_last4 or r_account

    biller_name = biller or (sender_domain.split(".")[0].title() if sender_domain else "Unknown")
    biller_category = _infer_category(sender_domain, biller_name)
    return {
        "biller_name": biller_name,
        "biller_name_normalized": normalize_biller_name(biller_name),
        "biller_category": biller_category,
        "amount_due": amount or Decimal("0.00"),
        "due_date": due_date,
        "account_number_last4": account_last4,
        "extraction_prompt_rev": EXTRACTION_PROMPT_REV,
    }
