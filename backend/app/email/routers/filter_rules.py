"""GmailFilterRule CRUD — Phase 15 EMAIL-04.

Endpoints:
  GET    /api/email/credentials/{cred_id}/filter-rules
  POST   /api/email/credentials/{cred_id}/filter-rules
  PATCH  /api/email/filter-rules/{id}
  DELETE /api/email/filter-rules/{id}

Open question #5 resolution (locked at schema layer in Plan 02): rules
are ordered by `priority ASC` so the lowest priority value wins. Tie-
break by id ASC (oldest rule wins).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_async_db
from app.email.models.credential import GmailCredential
from app.email.models.filter_rule import GmailFilterRule
from app.email.schemas.filter_rule import (
    GmailFilterRuleCreate,
    GmailFilterRuleResponse,
    GmailFilterRuleUpdate,
)

router = APIRouter(tags=["gmail-filter-rules"])


async def _require_credential(db: AsyncSession, credential_id: int) -> GmailCredential:
    cred = (
        await db.execute(
            select(GmailCredential).where(GmailCredential.id == credential_id)
        )
    ).scalar_one_or_none()
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )
    return cred


@router.get(
    "/credentials/{credential_id}/filter-rules",
    response_model=list[GmailFilterRuleResponse],
)
async def list_filter_rules(
    credential_id: int,
    db: AsyncSession = Depends(get_async_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """List filter rules ordered by priority ASC (open question #5)."""
    await _require_credential(db, credential_id)
    result = await db.execute(
        select(GmailFilterRule)
        .where(GmailFilterRule.credential_id == credential_id)
        .order_by(GmailFilterRule.priority.asc(), GmailFilterRule.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/credentials/{credential_id}/filter-rules",
    response_model=GmailFilterRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_filter_rule(
    credential_id: int,
    body: GmailFilterRuleCreate,
    db: AsyncSession = Depends(get_async_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Create a new filter rule for the credential."""
    await _require_credential(db, credential_id)
    rule = GmailFilterRule(
        credential_id=credential_id,
        **body.model_dump(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.patch(
    "/filter-rules/{rule_id}",
    response_model=GmailFilterRuleResponse,
)
async def update_filter_rule(
    rule_id: int,
    body: GmailFilterRuleUpdate,
    db: AsyncSession = Depends(get_async_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Patch a filter rule. Unset fields stay unchanged."""
    # SEC2: GmailFilterRule has no client_id; scope ownership via the parent
    # credential's client_id (join) in addition to RLS so a rule belonging to
    # another tenant cannot be mutated if the RLS context is misset.
    rule = (
        await db.execute(
            select(GmailFilterRule)
            .join(GmailCredential, GmailFilterRule.credential_id == GmailCredential.id)
            .where(
                GmailFilterRule.id == rule_id,
                GmailCredential.client_id == membership.client_id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Filter rule not found",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete(
    "/filter-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_filter_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_async_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Hard-delete a filter rule.

    SEC2: scope via the parent credential's client_id (join) in addition to
    RLS — GmailFilterRule has no client_id of its own.
    """
    rule = (
        await db.execute(
            select(GmailFilterRule)
            .join(GmailCredential, GmailFilterRule.credential_id == GmailCredential.id)
            .where(
                GmailFilterRule.id == rule_id,
                GmailCredential.client_id == membership.client_id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Filter rule not found",
        )
    await db.delete(rule)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
