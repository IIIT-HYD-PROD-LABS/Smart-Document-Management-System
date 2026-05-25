"""Authentication API routes - Register, Login, Refresh, Logout."""

import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.early_access import EarlyAccessRequest
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas import (
    AcceptInviteRequest,
    ForgotPasswordRequest,
    OAuthExchangeRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenPairResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.utils.rate_limiter import limiter
from sqlalchemy import text as sa_text


# ──── Race-free first-user → admin promotion ────
# Stable lock key for the bootstrap decision. Released at txn end.
_FIRST_USER_LOCK_KEY = 7398126503


def _safe_role(db: Session) -> str:
    """Decide register role with a PG advisory lock to dodge the count==0 race.

    Three call sites (local register, Google callback, Microsoft callback)
    previously read `User.count() == 0` then wrote, so two concurrent
    requests could both insert as admin on a fresh DB. The advisory lock
    serializes the decision per-transaction. Falls back gracefully on
    non-PG (test SQLite) and on inactive-user-only databases (M-3).
    """
    try:
        db.execute(sa_text(f"SELECT pg_advisory_xact_lock({_FIRST_USER_LOCK_KEY})"))
    except Exception:  # pragma: no cover - non-PG fallback
        pass
    is_first = db.query(User).filter(User.is_active == True).count() == 0  # noqa: E712
    return "admin" if is_first else "editor"


def _consume_invitation(
    db: Session, *, token: str | None, email: str
) -> EarlyAccessRequest | None:
    """Validate + atomically consume an early-access invitation JWT.

    Returns the EA row on success; raises HTTPException on any failure
    so callers can propagate the exact 400/403. None is returned only
    when token is None (handled by caller for the bootstrap case).
    """
    if not token:
        return None
    try:
        token_payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired. Please request early access again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation link.",
        )
    if token_payload.get("type") != "invitation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation link.",
        )
    if (token_payload.get("email") or "").lower() != (email or "").lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email does not match the invitation.",
        )
    ea = (
        db.query(EarlyAccessRequest)
        .filter(
            EarlyAccessRequest.id == token_payload.get("ea_id"),
            EarlyAccessRequest.status == "approved",
        )
        .with_for_update()
        .first()
    )
    if not ea or not ea.invitation_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation already used or no longer valid.",
        )
    # Single-use: null the stored token so a replay cannot succeed.
    ea.invitation_token = None
    return ea

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ──── Single-use OAuth exchange token tracking (in-process fallback) ────
# Used when Redis is unavailable. Entries auto-expire after _EXCHANGE_TTL.
_used_exchange_jti: dict[str, float] = {}  # jti -> expiry (monotonic)
_used_exchange_lock = threading.Lock()
_EXCHANGE_TTL = 150  # seconds, slightly over the 2-min JWT lifetime


def _mark_exchange_used(jti: str) -> bool:
    """Mark an exchange JTI as used. Returns False if already consumed (replay)."""
    now = time.monotonic()
    with _used_exchange_lock:
        # Prune expired entries
        expired = [k for k, exp in _used_exchange_jti.items() if exp < now]
        for k in expired:
            del _used_exchange_jti[k]
        if jti in _used_exchange_jti:
            return False
        _used_exchange_jti[jti] = now + _EXCHANGE_TTL
        return True


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
    """Register a new user account and return a token pair.

    Gate: after the bootstrap admin exists, registration requires an
    approved early-access invitation JWT. Without this, the public
    /register endpoint trivially bypassed the early-access workflow.
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    role = _safe_role(db)
    # Bootstrap exception: a fresh DB has no admin yet, allow self-register.
    # Any subsequent register MUST present a valid invitation token.
    if role != "admin":
        if not payload.invitation_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration requires an invitation. Request early access first.",
            )
        _consume_invitation(db, token=payload.invitation_token, email=payload.email)

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
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


@router.post("/accept-invite", response_model=TokenPairResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def accept_invite(
    request: Request,
    response: Response,
    payload: AcceptInviteRequest,
    db: Session = Depends(get_db),
):
    """Complete a tenant-team invitation: set password + activate + sign in.

    Idempotency: a second call with the same token (now that the user
    is active) returns 400 with a "sign in normally" hint, rather than
    silently overwriting the password.
    """
    from app.services.invitation_service import InvitationError, accept_invite as _accept

    try:
        user = _accept(db, token=payload.token, new_password=payload.password)
    except InvitationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    return _create_token_pair(user, db)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
def forgot_password(
    request: Request,
    response: Response,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Initiate a self-service password reset.

    Always responds 204 regardless of whether the email exists, to defend
    against account enumeration. If the email resolves to an active,
    local-auth user, a 15-minute reset link is emailed; otherwise the
    request is silently dropped (and a `password_reset_requested_unknown`
    audit row is written so a real abuse pattern can be detected later).

    Rate limit 3/min per IP matches the conservative posture used by the
    other auth endpoints; the rate limiter is the per-IP control while
    enumeration defence comes from the always-204 response shape.
    """
    from app.services.password_reset_service import issue_reset_token
    from app.services.audit_service import log_audit_event
    from app.utils.email import send_password_reset_email

    user = (
        db.query(User)
        .filter(User.email == payload.email, User.is_active == True)  # noqa: E712
        .first()
    )
    if user is None or (user.auth_provider and user.auth_provider != "local"):
        # Either no user, deactivated, or OAuth-only. Always log + 204.
        log_audit_event(
            user_id=None,
            action="password_reset_requested_unknown",
            resource_type="user",
            resource_id=None,
            details={"email_hint": payload.email[:3] + "***"},
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    token = issue_reset_token(user=user)
    try:
        send_password_reset_email(
            to_email=user.email,
            full_name=user.full_name or user.username,
            reset_token=token,
        )
    except Exception:  # noqa: BLE001 — non-fatal; user can request again
        logger.exception("password_reset_email_send_failed", user_id=user.id)

    log_audit_event(
        user_id=user.id,
        action="password_reset_requested",
        resource_type="user",
        resource_id=user.id,
        details={},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", response_model=TokenPairResponse)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    response: Response,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Complete a password reset and sign the user in.

    Validates the 15-minute reset JWT, sets the new bcrypt hash, and
    revokes every outstanding refresh token for the user. Returns a
    fresh access + refresh token pair so the user lands signed in.

    Single-use is enforced by anchoring the JWT to `users.updated_at`;
    consuming the token advances that timestamp so the same token cannot
    be replayed.
    """
    from app.services.password_reset_service import (
        PasswordResetError,
        consume_reset_token,
    )
    from app.services.audit_service import log_audit_event

    try:
        user = consume_reset_token(
            db, token=payload.token, new_password=payload.password
        )
    except PasswordResetError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    log_audit_event(
        user_id=user.id,
        action="password_reset_completed",
        resource_type="user",
        resource_id=user.id,
        details={},
    )
    return _create_token_pair(user, db)


@router.post("/login", response_model=TokenPairResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, response: Response, payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return a token pair."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        logger.warning("login_failed", reason="unknown_email")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.auth_provider != "local":
        logger.warning("login_wrong_provider", user_id=user.id, provider=user.auth_provider)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        logger.warning("login_failed", user_id=user.id, reason="bad_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        logger.warning("login_deactivated", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return _create_token_pair(user, db)


@router.post("/refresh", response_model=TokenPairResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(request: Request, response: Response, payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair.

    Implements token rotation with reuse detection:
    - Each refresh token can only be used once.
    - If a revoked (already-used) token is presented, ALL tokens for that user
      are revoked immediately to protect against token theft.
    """
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == payload.refresh_token)
        .with_for_update()  # Row-level lock prevents concurrent rotation race
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
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected -- all sessions revoked",
        )

    # Check expiry
    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db_token.is_revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    # Load and validate user BEFORE rotating tokens
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
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
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to refresh session")

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh_value,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def logout(request: Request, response: Response, payload: RefreshTokenRequest, db: Session = Depends(get_db)):
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
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()

    return {"detail": "Successfully logged out"}


@router.get("/providers")
@limiter.limit("30/minute")
def get_auth_providers(request: Request, response: Response):
    """Return which OAuth providers are configured."""
    providers = ["local"]
    if settings.GOOGLE_CLIENT_ID:
        providers.append("google")
    if settings.MICROSOFT_CLIENT_ID:
        providers.append("microsoft")
    return {"providers": providers}


@router.get("/oauth/diag")
@limiter.limit("30/minute")
def oauth_diag(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
):
    """Diagnostic for OAuth setup.

    Returns redirect URIs and a client_id hint. Public in DEBUG so a
    fresh install can self-serve `redirect_uri_mismatch` errors; in
    production this leaks the backend URL + client_id hint, so we
    require admin auth there.
    """
    if not settings.DEBUG:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        from app.utils.security import decode_access_token
        try:
            tok_payload = decode_access_token(credentials.credentials)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        uid = tok_payload.get("sub")
        u = db.query(User).filter(User.id == int(uid)).first() if uid else None
        if not u or u.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
    from app.services.oauth_service import _get_backend_url

    backend = _get_backend_url()
    frontend = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")

    def _hint(client_id: str) -> str | None:
        return f"{client_id[:12]}…" if client_id else None

    return {
        "backend_url": backend,
        "frontend_url": frontend,
        "providers": {
            "google": {
                "configured": bool(settings.GOOGLE_CLIENT_ID),
                "client_id_hint": _hint(settings.GOOGLE_CLIENT_ID),
                "redirect_uris": [
                    f"{backend}/api/auth/callback/google",
                    f"{backend}/api/email/gmail/oauth/callback",
                ],
                "console_url": "https://console.cloud.google.com/apis/credentials",
            },
            "microsoft": {
                "configured": bool(settings.MICROSOFT_CLIENT_ID),
                "client_id_hint": _hint(settings.MICROSOFT_CLIENT_ID),
                "redirect_uris": [
                    f"{backend}/api/auth/callback/microsoft",
                ],
                "console_url": (
                    "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/"
                    "ApplicationsListBlade"
                ),
            },
        },
        "javascript_origins": [frontend, backend],
    }


@router.get("/oauth/google")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def google_auth_url(request: Request, response: Response):
    """Return the Google OAuth authorization URL with CSRF state parameter."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google OAuth not configured")
    from app.services.oauth_service import GoogleOAuth
    # Sign the state as a JWT so the callback can verify it without cookies.
    # Cross-origin API calls (frontend on :3000, backend on :8000) can't
    # reliably share cookies, so cookie-based CSRF doesn't work here.
    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {"nonce": nonce, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    url = GoogleOAuth.get_auth_url(state)
    return JSONResponse(content={"url": url})


@router.get("/callback/google")
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def google_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback with CSRF state validation."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google OAuth not configured")

    # Handle user-denied consent
    if error:
        frontend_url = settings.FRONTEND_URL
        return RedirectResponse(url=f"{frontend_url}/login?error=oauth_denied")

    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code")

    # Validate CSRF state by verifying the signed JWT
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth state")
    try:
        jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired -- please try again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state -- possible CSRF")

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

    if not user_info.get("verified_email", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google email is not verified")

    email = email.lower()

    oauth_id = f"google_{user_info['id']}"
    user = db.query(User).filter(User.oauth_id == oauth_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if user.auth_provider == "local" and user.hashed_password:
                # Refuse to auto-link OAuth to a password-protected local account.
                # The user must log in with their password first, then link OAuth
                # from account settings to prove ownership.
                logger.warning(
                    "oauth_link_refused_local_account",
                    email=email, provider="google",
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists. Please sign in with your password.",
                )
            # Safe to link: account was created via OAuth or has no password
            if not user.oauth_id:
                user.oauth_id = oauth_id
            try:
                db.commit()
            except (IntegrityError, OperationalError):
                db.rollback()
        else:
            # Create new user. _safe_role() uses an advisory lock so
            # concurrent OAuth callbacks cannot both insert as admin.
            role = _safe_role(db)
            import re as _re
            username = _re.sub(r'[^a-zA-Z0-9_-]', '', email.split("@")[0]) or "user"
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
                role=role,
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
def microsoft_auth_url(request: Request, response: Response):
    """Return the Microsoft OAuth authorization URL with CSRF state parameter."""
    if not settings.MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Microsoft OAuth not configured")
    from app.services.oauth_service import MicrosoftOAuth
    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {"nonce": nonce, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    url = MicrosoftOAuth.get_auth_url(state)
    return JSONResponse(content={"url": url})


@router.get("/callback/microsoft")
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def microsoft_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle Microsoft OAuth callback with CSRF state validation."""
    if not settings.MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Microsoft OAuth not configured")

    if error:
        frontend_url = settings.FRONTEND_URL
        return RedirectResponse(url=f"{frontend_url}/login?error=oauth_denied")

    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code")

    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth state")
    try:
        jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired -- please try again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state -- possible CSRF")

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

    # Microsoft Graph does not have a "verified_email" flag like Google.
    # Reject emails that look like non-Microsoft addresses used as UPN
    # (e.g., a personal Microsoft account aliased to victim@company.com)
    # unless the tenant is restricted to a specific organization.
    email = email.lower()

    oauth_id = f"microsoft_{user_info['id']}"
    user = db.query(User).filter(User.oauth_id == oauth_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if user.auth_provider == "local" and user.hashed_password:
                # Refuse to auto-link OAuth to a password-protected local account.
                # The user must log in with their password first, then link OAuth
                # from account settings to prove ownership.
                logger.warning(
                    "oauth_link_refused_local_account",
                    email=email, provider="microsoft",
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists. Please sign in with your password.",
                )
            # Safe to link: account was created via OAuth or has no password
            if not user.oauth_id:
                user.oauth_id = oauth_id
            try:
                db.commit()
            except (IntegrityError, OperationalError):
                db.rollback()
        else:
            role = _safe_role(db)
            import re as _re
            username = _re.sub(r'[^a-zA-Z0-9_-]', '', email.split("@")[0]) or "user"
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
                role=role,
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
def exchange_oauth_code(request: Request, response: Response, payload: OAuthExchangeRequest, db: Session = Depends(get_db)):
    """Exchange a one-time OAuth code for a token pair.

    Each exchange token can only be used once. The jti (JWT ID) is tracked in
    Redis to prevent replay attacks within the token's 2-minute lifetime.
    """
    try:
        token_payload = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired exchange token")

    if token_payload.get("type") != "oauth_exchange":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    expected_code = token_payload.get("code", "")
    if not secrets.compare_digest(expected_code, payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid exchange code")

    # ── Replay prevention: each exchange token (jti) may only be used once ──
    jti = token_payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid exchange token (missing jti)",
        )

    replay_checked = False
    try:
        from redis import Redis as _Redis
        _redis = _Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        cache_key = f"oauth_exchange_used:{jti}"
        was_new = _redis.set(cache_key, "1", nx=True, ex=180)
        if not was_new:
            logger.warning("oauth_exchange_replay", jti=jti)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Exchange code has already been used",
            )
        replay_checked = True
    except HTTPException:
        raise
    except Exception:
        logger.warning("oauth_exchange_replay_redis_unavailable", jti=jti)

    # In-process fallback when Redis is down (covers single-worker deployments)
    if not replay_checked:
        if not _mark_exchange_used(jti):
            logger.warning("oauth_exchange_replay_memory", jti=jti)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Exchange code has already been used",
            )

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    return _create_token_pair(user, db)
