"""On-demand report generation — Phase 9 CLIENT-07 / D-19.

Phase 9 ships a JSON+HTML monthly compliance health summary.
Real PDF rendering (WeasyPrint or similar) is deferred to Phase 11/13
reporting; the response shape includes `summary_html` so a future
PDF-renderer can wrap it without changing the caller contract.

The report is generated synchronously per-request — no Celery — because
the queries are bounded by client_id + month and run in <50ms at
Phase 9 scale. Phase 11 will revisit if dataset growth warrants async.
"""
from sqlalchemy import extract
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

    summary_html = (
        "<html>"
        f"<head><title>Compliance Summary — {client.name} — {month}</title></head>"
        "<body>"
        "<h1>Compliance Health Summary</h1>"
        f"<h2>{client.name} — {month}</h2>"
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
