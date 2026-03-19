"""Admin API routes - User management and system stats."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentStatus
from app.schemas.admin import (
    AdminUserResponse,
    AdminUserListResponse,
    RoleUpdateRequest,
    StatusUpdateRequest,
    AdminStatsResponse,
)
from app.utils.security import require_admin
from app.utils.rate_limiter import limiter

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/users", response_model=AdminUserListResponse)
@limiter.limit("30/minute")
def list_users(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users (admin only)."""
    query = db.query(User)

    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{escaped}%"
        query = query.filter(
            (User.email.ilike(search_term)) |
            (User.username.ilike(search_term)) |
            (User.full_name.ilike(search_term))
        )

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    user_responses = []
    for u in users:
        doc_count = db.query(Document).filter(Document.user_id == u.id).count()
        user_responses.append(AdminUserResponse(
            id=u.id,
            email=u.email,
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            auth_provider=u.auth_provider,
            document_count=doc_count,
            created_at=u.created_at,
            updated_at=u.updated_at,
        ))

    return AdminUserListResponse(
        users=user_responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
@limiter.limit("30/minute")
def get_user_detail(
    request: Request,
    response: Response,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get user detail with document count (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    doc_count = db.query(Document).filter(Document.user_id == user.id).count()

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        document_count=doc_count,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/users/{user_id}/role")
@limiter.limit("10/minute")
def update_user_role(
    request: Request,
    response: Response,
    user_id: int,
    payload: RoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Change a user's role (admin only). Cannot demote self."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = user.role
    user.role = payload.role
    db.commit()

    logger.info("role_changed", user_id=user_id, old_role=old_role, new_role=payload.role, changed_by=current_user.id)

    return {"detail": f"Role updated from {old_role} to {payload.role}", "user_id": user_id}


@router.patch("/users/{user_id}/status")
@limiter.limit("10/minute")
def update_user_status(
    request: Request,
    response: Response,
    user_id: int,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Activate or deactivate a user (admin only). Cannot deactivate self."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own status",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = payload.is_active
    db.commit()

    status_str = "activated" if payload.is_active else "deactivated"
    logger.info("user_status_changed", user_id=user_id, status=status_str, changed_by=current_user.id)

    return {"detail": f"User {status_str}", "user_id": user_id}


@router.get("/stats", response_model=AdminStatsResponse)
@limiter.limit("20/minute")
def get_admin_stats(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get system-wide statistics (admin only)."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()

    users_by_role = {}
    for role in ("admin", "editor", "viewer"):
        count = db.query(User).filter(User.role == role).count()
        if count > 0:
            users_by_role[role] = count

    total_documents = db.query(Document).count()

    docs_by_status = {}
    for doc_status in DocumentStatus:
        count = db.query(Document).filter(Document.status == doc_status).count()
        if count > 0:
            docs_by_status[doc_status.value] = count

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        users_by_role=users_by_role,
        total_documents=total_documents,
        documents_by_status=docs_by_status,
    )
