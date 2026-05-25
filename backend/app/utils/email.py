"""Email sending utilities for early access approval/rejection."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import structlog

from app.config import settings

logger = structlog.stdlib.get_logger()


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Returns True on success, False on failure."""
    if not settings.SMTP_HOST:
        logger.warning(
            "email_skipped_no_smtp",
            to=to_email,
            subject=subject,
            hint="Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD in .env to enable email delivery",
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())

        logger.info("email_sent", to=to_email, subject=subject)
        return True
    except Exception as e:
        # Resend free-tier rejects every recipient that is not the account
        # owner with a 550 ("verify a domain at resend.com/domains"). That
        # is a configuration limitation, not a real outage, and the
        # alert/scheduler retries can flood the error log with it. Downgrade
        # the known-shape 550 to a warning so real send failures still
        # surface at ERROR.
        msg = str(e)
        is_resend_unverified = "550" in msg and (
            "verify a domain" in msg or "testing emails" in msg
        )
        log_fn = logger.warning if is_resend_unverified else logger.error
        log_fn(
            "email_send_failed",
            to=to_email,
            subject=subject,
            error=msg,
            hint=(
                "Resend rejects non-account-owner recipients on the free tier."
                " Verify a domain at resend.com/domains and update"
                " SMTP_FROM_EMAIL, or set FRONTEND_URL/SMTP_* to a provider"
                " that accepts arbitrary recipients."
            ) if is_resend_unverified else None,
        )
        return False


def send_approval_email(to_email: str, full_name: str, invitation_token: str) -> bool:
    """Send early access approval email with registration link.

    The query parameter must match what `/register` reads (`token`); a mismatch
    silently routes the user to the early-access gate even when the email lands.
    """
    registration_url = f"{settings.FRONTEND_URL}/register?token={invitation_token}"

    if not settings.SMTP_HOST and settings.DEBUG:
        logger.warning(
            "invitation_url_for_dev",
            to=to_email,
            full_name=full_name,
            url=registration_url,
            hint="SMTP not configured — copy this URL into a browser to test the flow locally",
        )

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="font-size: 20px; font-weight: 600; color: #111; margin: 0;">TaxSync</h1>
        </div>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">Hi {full_name},</p>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">
            Great news! Your early access request for <strong style="color: #111;">TaxSync</strong> has been approved.
        </p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{registration_url}" style="display: inline-block; padding: 12px 32px; background: #111; color: #fff; font-size: 14px; font-weight: 500; text-decoration: none; border-radius: 6px;">
                Create Your Account
            </a>
        </div>
        <p style="color: #999; font-size: 12px; line-height: 1.6;">
            This invitation link expires in 7 days. If you didn't request access, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;" />
        <p style="color: #bbb; font-size: 11px; text-align: center;">TaxSync &mdash; AI-powered tax compliance intelligence</p>
    </div>
    """

    return send_email(to_email, "Your TaxSync Early Access is Approved!", html)


def send_tenant_invite_email(
    *,
    to_email: str,
    invitee_name: str,
    inviter_name: str,
    client_name: str,
    invite_token: str,
) -> bool:
    """Send a tenant-team invitation email.

    The link lands on `${FRONTEND_URL}/accept-invite?token=<JWT>`. The
    invitee sets a password there; the backend flips is_active=True and
    issues access + refresh tokens.
    """
    accept_url = f"{settings.FRONTEND_URL}/accept-invite?token={invite_token}"

    if not settings.SMTP_HOST and settings.DEBUG:
        logger.warning(
            "tenant_invite_url_for_dev",
            to=to_email,
            invitee_name=invitee_name,
            inviter=inviter_name,
            client=client_name,
            url=accept_url,
            hint="SMTP not configured. Copy this URL into the browser to test the flow locally.",
        )

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="font-size: 20px; font-weight: 600; color: #111; margin: 0;">TaxSync</h1>
        </div>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">Hi {invitee_name},</p>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">
            <strong style="color: #111;">{inviter_name}</strong> invited you to join
            <strong style="color: #111;">{client_name}</strong> on TaxSync, the AI-powered tax compliance workspace.
        </p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{accept_url}" style="display: inline-block; padding: 12px 32px; background: #111; color: #fff; font-size: 14px; font-weight: 500; text-decoration: none; border-radius: 6px;">
                Accept invitation
            </a>
        </div>
        <p style="color: #999; font-size: 12px; line-height: 1.6;">
            This link expires in 7 days. After you click it, you will set your password and be signed in automatically.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;" />
        <p style="color: #bbb; font-size: 11px; text-align: center;">TaxSync, AI-powered tax compliance intelligence</p>
    </div>
    """

    return send_email(
        to_email,
        f"You are invited to join {client_name} on TaxSync",
        html,
    )


def send_password_reset_email(
    *,
    to_email: str,
    full_name: str,
    reset_token: str,
) -> bool:
    """Send a self-service password reset email.

    Land on `${FRONTEND_URL}/reset-password?token=<JWT>`. The user enters
    a new password there; backend validates the JWT (15-minute TTL,
    single-use) and replaces the bcrypt hash.
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    if not settings.SMTP_HOST and settings.DEBUG:
        logger.warning(
            "password_reset_url_for_dev",
            to=to_email,
            url=reset_url,
            hint="SMTP not configured. Copy this URL into the browser to complete the reset locally.",
        )

    safe_name = full_name or to_email.split("@", 1)[0]
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="font-size: 20px; font-weight: 600; color: #111; margin: 0;">TaxSync</h1>
        </div>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">Hi {safe_name},</p>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">
            We received a request to reset the password on your TaxSync account. Click the button below to choose a new one.
        </p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{reset_url}" style="display: inline-block; padding: 12px 32px; background: #111; color: #fff; font-size: 14px; font-weight: 500; text-decoration: none; border-radius: 6px;">
                Reset password
            </a>
        </div>
        <p style="color: #999; font-size: 12px; line-height: 1.6;">
            This link expires in 15 minutes and can only be used once. If you did not request this reset, you can safely ignore this email; your password will not change.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;" />
        <p style="color: #bbb; font-size: 11px; text-align: center;">TaxSync, AI-powered tax compliance intelligence</p>
    </div>
    """

    ok = send_email(to_email, "Reset your TaxSync password", html)
    if not ok:
        # Email delivery failed (Resend sandbox restriction, SMTP not
        # configured, transient outage, etc.). The user is locked out
        # unless an operator can hand-deliver the link. Log the URL at
        # WARNING with a clear hint so an admin with log access can
        # ship it to the user out-of-band. Log access is already a
        # full-admin capability, so this does not widen the trust
        # boundary.
        logger.warning(
            "password_reset_url_fallback",
            to=to_email,
            url=reset_url,
            hint=(
                "Email delivery failed. Send this URL to the user manually "
                "(it expires in 15 minutes). Fix the SMTP misconfiguration "
                "(Resend: verify a domain at resend.com/domains and update "
                "SMTP_FROM_EMAIL) so future resets self-deliver."
            ),
        )
    return ok


def send_rejection_email(to_email: str, full_name: str, note: str | None = None) -> bool:
    """Send early access rejection email."""
    note_html = f'<p style="color: #555; font-size: 14px; line-height: 1.6;"><em>Note from our team: {note}</em></p>' if note else ""

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="font-size: 20px; font-weight: 600; color: #111; margin: 0;">TaxSync</h1>
        </div>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">Hi {full_name},</p>
        <p style="color: #555; font-size: 14px; line-height: 1.6;">
            Thank you for your interest in TaxSync. Unfortunately, we're unable to approve your early access request at this time.
        </p>
        {note_html}
        <p style="color: #555; font-size: 14px; line-height: 1.6;">
            You're welcome to apply again in the future.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;" />
        <p style="color: #bbb; font-size: 11px; text-align: center;">TaxSync &mdash; AI-powered tax compliance intelligence</p>
    </div>
    """

    return send_email(to_email, "TaxSync Early Access Update", html)
