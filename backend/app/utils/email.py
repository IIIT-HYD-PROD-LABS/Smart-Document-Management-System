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
        logger.warning("email_skipped_no_smtp", to=to_email, subject=subject)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())

        logger.info("email_sent", to=to_email, subject=subject)
        return True
    except Exception as e:
        logger.error("email_send_failed", to=to_email, error=str(e))
        return False


def send_approval_email(to_email: str, full_name: str, invitation_token: str) -> bool:
    """Send early access approval email with registration link."""
    registration_url = f"{settings.FRONTEND_URL}/register?invite={invitation_token}"

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
