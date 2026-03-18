"""Authentication API routes - Register, Login, Refresh, Logout."""

import secrets
from datetime import datetime, timedelta, timezone

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError, OperationalError
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
    OAuthExchangeRequest,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.utils.rate_limiter import limiter

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _create_token_pair(user: User, db: Session) -> TokenPairResponse:
    """Create an access + refresh token pair for a user and persist the refresh token."""
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    refresh_token_value, expires_at = create_refresh_token()

    db_refresh_token = RefreshToken(
        token=refresh_token_value,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to create session")

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

    # First user becomes admin automatically
    is_first_user = db.query(User).count() == 0
    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="admin" if is_first_user else "editor",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already registered")
    except OperationalError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable")
    db.refresh(user)

    return _create_token_pair(user, db)


@router.post("/login", response_model=TokenPairResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, response: Response, payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return a token pair."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        logger.warning("login_failed", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.auth_provider != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This account uses {user.auth_provider} login. Please use the {user.auth_provider} button to sign in.",
        )

    if not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        logger.warning("login_failed", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return _create_token_pair(user, db)


@router.post("/refresh", response_model=TokenPairResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(request: Request, payload: RefreshTokenRequest, db: Session = Depends(get_db)):
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

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh_value,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def logout(request: Request, payload: RefreshTokenRequest, db: Session = Depends(get_db)):
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


@router.get("/providers")
def get_auth_providers():
    """Return which OAuth providers are configured."""
    providers = ["local"]
    if settings.GOOGLE_CLIENT_ID:
        providers.append("google")
    if settings.MICROSOFT_CLIENT_ID:
        providers.append("microsoft")
    return {"providers": providers}


@router.get("/oauth/google")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def google_auth_url(request: Request):
    """Return the Google OAuth authorization URL."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google OAuth not configured")
    from app.services.oauth_service import GoogleOAuth
    url = GoogleOAuth.get_auth_url()
    return {"url": url}


@router.get("/callback/google")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google OAuth not configured")
    from app.services.oauth_service import GoogleOAuth

    try:
        token_data = await GoogleOAuth.exchange_code(code)
        user_info = await GoogleOAuth.get_user_info(token_data["access_token"])
    except Exception as e:
        logger.error("google_oauth_failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to authenticate with Google")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not provided by Google")

    oauth_id = f"google_{user_info['id']}"
    user = db.query(User).filter(User.oauth_id == oauth_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Link OAuth to existing account but keep original auth_provider
            # so password login still works
            if not user.oauth_id:
                user.oauth_id = oauth_id
            db.commit()
        else:
            # Create new user
            is_first_user = db.query(User).count() == 0
            username = email.split("@")[0]
            # Ensure unique username
            base_username = username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1
            user = User(
                email=email,
                username=username,
                full_name=user_info.get("name"),
                auth_provider="google",
                oauth_id=oauth_id,
                role="admin" if is_first_user else "editor",
            )
            try:
                db.add(user)
                db.commit()
                db.refresh(user)
            except IntegrityError:
                db.rollback()
                # User was created by a concurrent request, re-fetch
                user = db.query(User).filter(User.email == email).first()
                if not user:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Account creation failed")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    # Generate a one-time exchange code
    exchange_code = secrets.token_urlsafe(32)
    # Store in a short-lived token
    exchange_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "type": "oauth_exchange", "code": exchange_code},
        expires_delta=timedelta(minutes=2),
    )

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(url=f"{frontend_url}/oauth/callback?code={exchange_code}&token={exchange_token}")


@router.get("/oauth/microsoft")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def microsoft_auth_url(request: Request):
    """Return the Microsoft OAuth authorization URL."""
    if not settings.MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Microsoft OAuth not configured")
    from app.services.oauth_service import MicrosoftOAuth
    url = MicrosoftOAuth.get_auth_url()
    return {"url": url}


@router.get("/callback/microsoft")
async def microsoft_callback(code: str, db: Session = Depends(get_db)):
    """Handle Microsoft OAuth callback."""
    if not settings.MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Microsoft OAuth not configured")
    from app.services.oauth_service import MicrosoftOAuth

    try:
        token_data = await MicrosoftOAuth.exchange_code(code)
        user_info = await MicrosoftOAuth.get_user_info(token_data["access_token"])
    except Exception as e:
        logger.error("microsoft_oauth_failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to authenticate with Microsoft")

    email = user_info.get("mail") or user_info.get("userPrincipalName")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not provided by Microsoft")

    oauth_id = f"microsoft_{user_info['id']}"
    user = db.query(User).filter(User.oauth_id == oauth_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Link OAuth to existing account but keep original auth_provider
            # so password login still works
            if not user.oauth_id:
                user.oauth_id = oauth_id
            db.commit()
        else:
            is_first_user = db.query(User).count() == 0
            username = email.split("@")[0]
            base_username = username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1
            user = User(
                email=email,
                username=username,
                full_name=user_info.get("displayName"),
                auth_provider="microsoft",
                oauth_id=oauth_id,
                role="admin" if is_first_user else "editor",
            )
            try:
                db.add(user)
                db.commit()
                db.refresh(user)
            except IntegrityError:
                db.rollback()
                # User was created by a concurrent request, re-fetch
                user = db.query(User).filter(User.email == email).first()
                if not user:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Account creation failed")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    exchange_code = secrets.token_urlsafe(32)
    exchange_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "type": "oauth_exchange", "code": exchange_code},
        expires_delta=timedelta(minutes=2),
    )

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(url=f"{frontend_url}/oauth/callback?code={exchange_code}&token={exchange_token}")


@router.post("/oauth/exchange", response_model=TokenPairResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def exchange_oauth_code(request: Request, payload: OAuthExchangeRequest, db: Session = Depends(get_db)):
    """Exchange a one-time OAuth code for a token pair."""
    try:
        token_payload = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired exchange token")

    if token_payload.get("type") != "oauth_exchange":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    if token_payload.get("code") != payload.code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid exchange code")

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    return _create_token_pair(user, db)
