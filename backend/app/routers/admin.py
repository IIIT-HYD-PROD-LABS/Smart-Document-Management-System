"""Admin API routes - User management, system stats, and early access management."""

from datetime import date, datetime, timedelta, timezone

import jwt
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path as PathParam, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.audit_log import AuditLog
from app.models.early_access import EarlyAccessRequest
from app.schemas.admin import (
    AdminUserResponse,
    AdminUserListResponse,
    RoleUpdateRequest,
    StatusUpdateRequest,
    AdminStatsResponse,
)
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.schemas.early_access import EarlyAccessResponse, EarlyAccessListResponse, EarlyAccessReviewRequest
from app.utils.security import require_admin
from app.utils.email import send_approval_email, send_rejection_email
from app.services.audit_service import log_audit_event
from app.utils.rate_limiter import limiter

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/users", response_model=AdminUserListResponse)
@limiter.limit("30/minute")
def list_users(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1, le=10000),
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

    # Single query with LEFT JOIN subquery to count documents per user,
    # avoiding N+1 (previously ran a separate COUNT per user).
    doc_count_subq = (
        db.query(
            Document.user_id,
            func.count(Document.id).label("doc_count"),
        )
        .group_by(Document.user_id)
        .subquery()
    )
    users_with_counts = (
        query
        .outerjoin(doc_count_subq, User.id == doc_count_subq.c.user_id)
        .add_columns(func.coalesce(doc_count_subq.c.doc_count, 0).label("doc_count"))
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    user_responses = []
    for u, doc_count in users_with_counts:
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
    user_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get user detail with document count (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    doc_count = db.query(func.count(Document.id)).filter(Document.user_id == user.id).scalar()

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
    payload: RoleUpdateRequest,
    background_tasks: BackgroundTasks,
    user_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Change a user's role (admin only). Cannot demote self or remove the last admin."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent removing the last active admin
    if user.role == "admin" and payload.role != "admin":
        admin_count = db.query(func.count(User.id)).filter(
            User.role == "admin", User.is_active == True  # noqa: E712
        ).scalar()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last admin. Promote another user to admin first.",
            )

    old_role = user.role
    user.role = payload.role
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to update role")

    logger.info("role_changed", user_id=user_id, old_role=old_role, new_role=payload.role, changed_by=current_user.id)

    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="role_change",
        resource_type="user", resource_id=user_id,
        details={"old_role": old_role, "new_role": payload.role},
        ip_address=request.client.host if request.client else None,
    )

    return {"detail": f"Role updated from {old_role} to {payload.role}", "user_id": user_id}


@router.patch("/users/{user_id}/status")
@limiter.limit("10/minute")
def update_user_status(
    request: Request,
    response: Response,
    payload: StatusUpdateRequest,
    background_tasks: BackgroundTasks,
    user_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Activate or deactivate a user (admin only). Cannot deactivate self or the last admin."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own status",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deactivating the last active admin
    if user.role == "admin" and not payload.is_active:
        admin_count = db.query(func.count(User.id)).filter(
            User.role == "admin", User.is_active == True  # noqa: E712
        ).scalar()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last admin. Promote another user to admin first.",
            )

    user.is_active = payload.is_active

    # Revoke all active refresh tokens when deactivating a user
    if not payload.is_active:
        from app.models.refresh_token import RefreshToken
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        ).update(
            {
                "is_revoked": True,
                "revoked_at": datetime.now(timezone.utc),
            }
        )

    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to update user status")

    status_str = "activated" if payload.is_active else "deactivated"
    logger.info("user_status_changed", user_id=user_id, status=status_str, changed_by=current_user.id)

    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="status_change",
        resource_type="user", resource_id=user_id,
        details={"new_status": "activated" if payload.is_active else "deactivated"},
        ip_address=request.client.host if request.client else None,
    )

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
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()  # noqa: E712

    # Single GROUP BY instead of one COUNT per role
    role_rows = (
        db.query(User.role, func.count(User.id))
        .group_by(User.role)
        .all()
    )
    users_by_role = {role: count for role, count in role_rows if count > 0}

    total_documents = db.query(func.count(Document.id)).scalar()

    # Single GROUP BY instead of one COUNT per status
    status_rows = (
        db.query(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )
    docs_by_status = {s.value: count for s, count in status_rows if count > 0}

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        users_by_role=users_by_role,
        total_documents=total_documents,
        documents_by_status=docs_by_status,
    )


@router.get("/audit", response_model=AuditLogListResponse)
@limiter.limit("30/minute")
def list_audit_logs(
    request: Request,
    response: Response,
    user_id: int | None = Query(None, ge=1),
    action: str | None = Query(None, max_length=100),
    resource_type: str | None = Query(None, max_length=100),
    resource_id: int | None = Query(None, ge=1),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Query audit logs with optional filters (admin only)."""
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if resource_type is not None:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        query = query.filter(AuditLog.resource_id == resource_id)
    if date_from is not None:
        query = query.filter(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc))
    if date_to is not None:
        query = query.filter(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc))

    total = query.count()

    items = (
        query
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        per_page=per_page,
    )


# ──── Early Access Management ────


@router.get("/early-access", response_model=EarlyAccessListResponse)
@limiter.limit("30/minute")
def list_early_access(
    request: Request,
    response: Response,
    status_filter: str | None = Query(None, alias="status_filter", pattern=r"^(pending|approved|rejected)$"),
    search: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List early access requests (admin only)."""
    query = db.query(EarlyAccessRequest)

    if status_filter:
        query = query.filter(EarlyAccessRequest.status == status_filter)

    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{escaped}%"
        query = query.filter(
            (EarlyAccessRequest.email.ilike(search_term))
            | (EarlyAccessRequest.full_name.ilike(search_term))
            | (EarlyAccessRequest.company.ilike(search_term))
        )

    total = query.count()
    items = (
        query
        .order_by(EarlyAccessRequest.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return EarlyAccessListResponse(
        items=[EarlyAccessResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/early-access/stats")
@limiter.limit("30/minute")
def get_early_access_stats(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get early access request counts by status (admin only)."""
    rows = (
        db.query(EarlyAccessRequest.status, func.count(EarlyAccessRequest.id))
        .group_by(EarlyAccessRequest.status)
        .all()
    )
    counts = {s: c for s, c in rows}
    return {
        "pending": counts.get("pending", 0),
        "approved": counts.get("approved", 0),
        "rejected": counts.get("rejected", 0),
        "total": sum(counts.values()),
    }


@router.patch("/early-access/{request_id}")
@limiter.limit("10/minute")
def review_early_access(
    request: Request,
    response: Response,
    payload: EarlyAccessReviewRequest,
    background_tasks: BackgroundTasks,
    request_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Approve or reject an early access request (admin only)."""
    ea_request = db.query(EarlyAccessRequest).filter(EarlyAccessRequest.id == request_id).first()
    if not ea_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early access request not found")

    if ea_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request has already been {ea_request.status}",
        )

    ea_request.status = payload.status
    ea_request.admin_note = payload.admin_note
    ea_request.reviewed_at = datetime.now(timezone.utc)
    ea_request.reviewed_by = current_user.id

    invitation_token = None
    if payload.status == "approved":
        invitation_token = jwt.encode(
            {
                "type": "invitation",
                "email": ea_request.email,
                "ea_id": ea_request.id,
                "exp": datetime.now(timezone.utc) + timedelta(days=7),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        ea_request.invitation_token = invitation_token

    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to update request",
        )

    logger.info("early_access_reviewed", request_id=request_id, status=payload.status, admin=current_user.id)

    if payload.status == "approved" and invitation_token:
        background_tasks.add_task(send_approval_email, ea_request.email, ea_request.full_name, invitation_token)
    elif payload.status == "rejected":
        background_tasks.add_task(send_rejection_email, ea_request.email, ea_request.full_name, payload.admin_note)

    background_tasks.add_task(
        log_audit_event,
        user_id=current_user.id,
        action=f"early_access_{payload.status}",
        resource_type="early_access",
        resource_id=request_id,
        details={"email": ea_request.email, "admin_note": payload.admin_note},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "detail": f"Early access request {payload.status}",
        "request_id": request_id,
        "email": ea_request.email,
    }
