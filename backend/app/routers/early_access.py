"""Early Access API routes - Public submission and invitation validation."""

import jwt as pyjwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.early_access import EarlyAccessRequest
from app.models.user import User
from app.schemas.early_access import EarlyAccessSubmit
from app.utils.rate_limiter import limiter

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/early-access", tags=["Early Access"])


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def submit_early_access(
    request: Request,
    response: Response,
    payload: EarlyAccessSubmit,
    db: Session = Depends(get_db),
):
    """Submit an early access request (public, no auth required)."""
    existing = (
        db.query(EarlyAccessRequest)
        .filter(
            EarlyAccessRequest.email == payload.email,
            EarlyAccessRequest.status.in_(["pending", "approved"]),
        )
        .first()
    )
    if existing:
        if existing.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email has already been approved. Check your email for the registration link.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An early access request for this email is already pending.",
        )

    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    ea_request = EarlyAccessRequest(
        full_name=payload.full_name,
        email=payload.email,
        company=payload.company,
        reason=payload.reason,
    )
    db.add(ea_request)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to submit request. Please try again.",
        )

    logger.info("early_access_submitted", email=payload.email)

    return {
        "detail": "Your early access request has been submitted. We'll review it and get back to you soon.",
    }


@router.get("/validate-invite")
@limiter.limit("10/minute")
def validate_invitation(
    request: Request,
    response: Response,
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """Validate an invitation token and return pre-fill data for registration."""
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired. Please request early access again.",
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation link.",
        )

    if payload.get("type") != "invitation":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation link.")

    email = payload.get("email")
    ea_id = payload.get("ea_id")

    if not email or not ea_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation link.")

    ea_request = (
        db.query(EarlyAccessRequest)
        .filter(
            EarlyAccessRequest.id == ea_id,
            EarlyAccessRequest.status == "approved",
        )
        .first()
    )
    if not ea_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation is no longer valid.",
        )

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists. Please sign in.",
        )

    return {"valid": True, "email": email, "full_name": ea_request.full_name}
