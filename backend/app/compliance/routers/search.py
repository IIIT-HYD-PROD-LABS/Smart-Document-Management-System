"""Phase 13 unified search router — /api/compliance/search/unified.

v2.0 implementation backs onto PostgreSQL FTS. v2.1 swaps the underlying
service to Elasticsearch without touching this surface.

Hardening (CRIT-1 second pass): the router now passes the authenticated
user_id into the search service so documents results are scoped by
ownership/sharing. This closes a cross-user document leak.
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.compliance.services.unified_search_service import (
    UnifiedSearchHit,
    search,
)
from app.database import get_async_db
from app.models.user import User
from app.utils.security import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["compliance-search"])


class UnifiedSearchHitOut(BaseModel):
    entity_type: Literal["notice", "document"]
    entity_id: int
    rank: float
    title: str
    snippet: str
    metadata: dict


class UnifiedSearchResponse(BaseModel):
    items: list[UnifiedSearchHitOut]
    query: str
    page: int
    page_size: int
    backend: str  # 'postgres-fts' in v2.0; 'elasticsearch' in v2.1


@router.get(
    "/unified",
    response_model=UnifiedSearchResponse,
    summary="Cross-entity search across compliance_notices + documents",
)
async def unified_search(
    # min_length=2: PostgreSQL FTS with 1-char tokens (e.g. "a") falls back
    # to a sequential scan because GIN indexes don't store single-char
    # lexemes by default. 2 is the minimum that reliably uses the index.
    q: str = Query(..., min_length=2, max_length=200),
    entity_types: str = Query(
        "notice,document",
        description="Comma-separated subset of {notice, document}",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    types_list = [
        t.strip()
        for t in entity_types.split(",")
        if t.strip() in ("notice", "document")
    ]
    try:
        hits: list[UnifiedSearchHit] = await search(
            db,
            query=q,
            user_id=int(current_user.id),
            entity_types=types_list,
            page=page,
            page_size=page_size,
        )
    except SQLAlchemyError:
        # Hardening (F4) — surface a 503 instead of FastAPI default 500.
        # Sanitize the user query before logging: strip control chars and
        # cap length to defang log-injection payloads (CodeQL py/log-injection).
        safe_q = "".join(ch for ch in (q or "") if ch.isprintable())[:120]
        logger.exception("unified_search_failed: q=%r user_id=%s", safe_q, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search temporarily unavailable; please retry.",
        )
    return UnifiedSearchResponse(
        items=[UnifiedSearchHitOut(**h.__dict__) for h in hits],
        query=q,
        page=page,
        page_size=page_size,
        backend="postgres-fts",
    )
