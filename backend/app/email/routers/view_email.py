"""On-demand 'View source email' endpoint — Phase 15 D-18 + D-37.

Endpoint:
  GET /api/email/messages/{message_log_id}/view

Resolves GmailMessageLog -> GmailCredential, then invokes the MCP
`gmail_read_message` tool to fetch the body via Gmail API. Body is
NEVER cached or persisted (D-34: fetch-once-discard).

The MCP tool itself writes a PII-redacted MCP_TOOL_CALL audit row
(D-35, D-36); this router does not write its own audit entry to avoid
double-counting.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db
from app.email.mcp.client import call_gmail_tool
from app.email.models.credential import GmailCredential
from app.email.models.message_log import GmailMessageLog

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gmail-view"])


@router.get("/messages/{message_log_id}/view")
async def view_email(
    message_log_id: int,
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Fetch and return the source email body via MCP gmail_read_message.

    Per D-34 the body lives only in the response payload; no DB or Redis
    persistence. Per D-37 this is invoked by the bill detail page deep-link
    and the compliance notice detail page deep-link.
    """
    log = (
        db.query(GmailMessageLog)
        .filter(GmailMessageLog.id == message_log_id)
        .first()
    )
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message log not found",
        )
    cred = (
        db.query(GmailCredential)
        .filter(GmailCredential.id == log.credential_id)
        .first()
    )
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )
    if cred.status != GmailCredential.STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Credential not active (status: {cred.status})",
        )
    try:
        return await call_gmail_tool(
            "gmail_read_message",
            {
                "user_id": cred.user_id,
                "client_id": cred.client_id,
                "message_id": log.gmail_message_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — surface as 502 with type only
        logger.exception(
            "gmail_read_message_failed message_log_id=%s", message_log_id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail tool invocation failed: {type(e).__name__}",
        )
