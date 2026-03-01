"""Authentication API routes - Register, Login, Refresh, Logout."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenPairResponse,
    RefreshTokenRequest,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.utils.rate_limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _create_token_pair(user: User, db: Session) -> TokenPairResponse:
    """Create an access + refresh token pair for a user and persist the refresh token."""
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_value, expires_at = create_refresh_token()

    db_refresh_token = RefreshToken(
        token=refresh_token_value,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    db.commit()

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register(request: Request, response: Response, payload: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account and return a token pair."""
    # Check for existing email
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    # Check for existing username
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _create_token_pair(user, db)


@router.post("/login", response_model=TokenPairResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, response: Response, payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return a token pair."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return _create_token_pair(user, db)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair.

    Implements token rotation with reuse detection:
    - Each refresh token can only be used once.
    - If a revoked (already-used) token is presented, ALL tokens for that user
      are revoked immediately to protect against token theft.
    """
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == payload.refresh_token)
        .first()
    )

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Reuse detection: if a revoked token is presented, an attacker may have
    # stolen the token chain. Revoke ALL tokens for this user.
    if db_token.is_revoked:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == db_token.user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        ).update(
            {
                "is_revoked": True,
                "revoked_at": datetime.now(timezone.utc),
            }
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected -- all sessions revoked",
        )

    # Check expiry
    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db_token.is_revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    # Rotate: revoke old token, issue new pair
    new_refresh_value, new_expires_at = create_refresh_token()

    db_token.is_revoked = True
    db_token.revoked_at = datetime.now(timezone.utc)
    db_token.replaced_by = new_refresh_value

    new_db_token = RefreshToken(
        token=new_refresh_value,
        user_id=db_token.user_id,
        expires_at=new_expires_at,
    )
    db.add(new_db_token)
    db.commit()

    # Load user for the response
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh_value,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Revoke the provided refresh token (server-side logout)."""
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == payload.refresh_token)
        .first()
    )

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if not db_token.is_revoked:
        db_token.is_revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return {"detail": "Successfully logged out"}
