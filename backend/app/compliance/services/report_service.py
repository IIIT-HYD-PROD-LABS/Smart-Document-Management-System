"""On-demand report generation — Phase 9 CLIENT-07 / D-19 + Phase 13 v2.0
analytics aggregations.

H-K second hardening: `client.name` and `month` are user-supplied data
that get interpolated into `summary_html`. Today the frontend renders
this inside `<pre>` (text-content), so XSS is blocked. But the
`summary_html` field is documented as a future PDF-renderer contract;
any future rendering path that interprets it as HTML would be
exploitable. We escape at the source so the output is XSS-safe by
construction regardless of how it's later rendered.

Phase 9 ships a JSON+HTML monthly compliance health summary.

Phase 13 v2.0 adds three aggregation queries powering the analytics
tabs on the reports page.
"""
import html
from datetime import datetime, timedelta, timezone

from sqlalchemy import extract, func, text
from sqlalchemy.orm import Session

from app.compliance.models.client import Client
from app.compliance.models.notice import ComplianceNotice


def generate_health_summary(
    db: Session, client_id: int, month: str
) -> dict:
    """Generate a monthly compliance health summary.

    `month` format: 'YYYY-MM' (e.g. '2026-04'). Returns:

        {
          "client_id": int,
          "month": str,
          "metrics": {
            "notices_received": int,    # created_at within month
            "notices_resolved": int,    # status_changed_at within month
                                        # AND status == 'resolved'
            "outstanding": int,         # max(0, received - resolved)
          },
          "summary_html": str,          # human-readable HTML body
        }

    Raises ValueError on malformed `month` or unknown `client_id`.
    """
    try:
        year_str, month_str = month.split("-")
        year = int(year_str)
        month_num = int(month_str)
        if not (1 <= month_num <= 12):
            raise ValueError("month out of range")
    except Exception as exc:
        raise ValueError(
            f"Invalid month format: {month}. Use 'YYYY-MM'."
        ) from exc

    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        raise ValueError(f"Client {client_id} not found")

    # Notices created in the month
    notices_in_month = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.client_id == client_id,
            extract("year", ComplianceNotice.created_at) == year,
            extract("month", ComplianceNotice.created_at) == month_num,
        )
        .count()
    )

    # Notices resolved in the month (status_changed_at within window)
    resolved = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.client_id == client_id,
            ComplianceNotice.status == "resolved",
            extract("year", ComplianceNotice.status_changed_at) == year,
            extract("month", ComplianceNotice.status_changed_at)
            == month_num,
        )
        .count()
    )

    metrics = {
        "notices_received": notices_in_month,
        "notices_resolved": resolved,
        "outstanding": max(0, notices_in_month - resolved),
    }

    # H-K — escape user-controlled fields before HTML interpolation.
    safe_name = html.escape(client.name or "")
    safe_month = html.escape(month)
    summary_html = (
        "<html>"
        f"<head><title>Compliance Summary — {safe_name} — {safe_month}</title></head>"
        "<body>"
        "<h1>Compliance Health Summary</h1>"
        f"<h2>{safe_name} — {safe_month}</h2>"
        "<ul>"
        f"<li>Notices received this month: {metrics['notices_received']}</li>"
        f"<li>Notices resolved this month: {metrics['notices_resolved']}</li>"
        f"<li>Outstanding at month-end: {metrics['outstanding']}</li>"
        "</ul>"
        "</body></html>"
    )

    return {
        "client_id": client_id,
        "month": month,
        "metrics": metrics,
        "summary_html": summary_html,
    }


# ──────────────────────────────────────────────────────────────────────
# Phase 13 v2.0 — analytics aggregations
# ──────────────────────────────────────────────────────────────────────

def _window_start(window_days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=window_days)


def penalty_by_authority(
    db: Session, *, client_id: int, window_days: int = 90
) -> list[dict]:
    """Sum + count of notices grouped by authority over the rolling window.

    Returns one row per authority that had at least one notice in the
    window. `total_penalty` and `total_tax_demand` are returned as
    floats (Decimal does not serialize to JSON natively without a
    custom encoder; the precision loss at INR scale is immaterial for
    analytics displays).
    """
    cutoff = _window_start(window_days)
    rows = (
        db.query(
            ComplianceNotice.authority,
            func.count(ComplianceNotice.id).label("count"),
            func.coalesce(
                func.sum(ComplianceNotice.penalty), 0
            ).label("total_penalty"),
            func.coalesce(
                func.sum(ComplianceNotice.tax_demand), 0
            ).label("total_tax_demand"),
        )
        .filter(
            ComplianceNotice.client_id == client_id,
            ComplianceNotice.created_at >= cutoff,
        )
        .group_by(ComplianceNotice.authority)
        .order_by(func.sum(ComplianceNotice.penalty).desc().nulls_last())
        .all()
    )
    return [
        {
            "authority": r.authority,
            "count": int(r.count),
            "total_penalty": float(r.total_penalty or 0),
            "total_tax_demand": float(r.total_tax_demand or 0),
        }
        for r in rows
    ]


def notice_volume_by_status(
    db: Session, *, client_id: int, window_days: int = 90
) -> list[dict]:
    """Notice counts grouped by status over the rolling window."""
    cutoff = _window_start(window_days)
    rows = (
        db.query(
            ComplianceNotice.status,
            func.count(ComplianceNotice.id).label("count"),
        )
        .filter(
            ComplianceNotice.client_id == client_id,
            ComplianceNotice.created_at >= cutoff,
        )
        .group_by(ComplianceNotice.status)
        .all()
    )
    return [{"status": r.status, "count": int(r.count)} for r in rows]


def response_time_distribution(
    db: Session, *, client_id: int, window_days: int = 90
) -> dict:
    """Response time distribution for resolved/submitted notices in window.

    Computed as `status_changed_at - created_at` in days. Returns
    {p50, p90, p95, mean, count} or zeros if no resolved notices exist.
    """
    cutoff = _window_start(window_days)
    sql = text(
        """
        WITH durations AS (
            SELECT
                EXTRACT(EPOCH FROM (status_changed_at - created_at)) / 86400.0
                    AS days
            FROM compliance_notices
            WHERE client_id = :cid
              AND created_at >= :cutoff
              AND status IN ('resolved', 'submitted')
              AND status_changed_at IS NOT NULL
        )
        SELECT
            percentile_cont(0.5)  WITHIN GROUP (ORDER BY days) AS p50,
            percentile_cont(0.9)  WITHIN GROUP (ORDER BY days) AS p90,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY days) AS p95,
            AVG(days) AS mean,
            COUNT(*) AS count
        FROM durations
        """
    )
    row = db.execute(sql, {"cid": client_id, "cutoff": cutoff}).fetchone()
    if row is None or row.count == 0:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "mean": 0.0, "count": 0}
    return {
        "p50": float(row.p50 or 0.0),
        "p90": float(row.p90 or 0.0),
        "p95": float(row.p95 or 0.0),
        "mean": float(row.mean or 0.0),
        "count": int(row.count),
    }
