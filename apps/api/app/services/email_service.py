"""Email service abstraction over Resend API with console fallback.

Uses ``httpx.AsyncClient`` to call the Resend HTTP API directly (cleaner
than the SDK's global-api-key pattern).  When ``EMAIL_PROVIDER_API_KEY``
is not set, falls back to logging emails via structlog — useful for
development and testing where real email delivery is unwanted.

Each public function returns an ``EmailResult`` dataclass; callers
check ``.success`` rather than relying on exceptions.  Transient
errors are logged and return ``success=False``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ruff: noqa: E501 — HTML template lines exceed 100 chars by design

_RESEND_API_URL = "https://api.resend.com/emails"
_EMAIL_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class EmailResult:
    """Outcome of an email send attempt.

    Attributes:
        success: ``True`` if the email was accepted for delivery.
        message_id: Resend message ID (``"console-fallback"`` in dev/test).
        error: Human-readable error reason, or ``None`` on success.
    """

    success: bool
    message_id: str = ""
    error: str | None = None


# ── Core send function ────────────────────────────────────────────────────────


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    text: str | None = None,
) -> EmailResult:
    """Deliver an email via Resend or the console fallback.

    Args:
        to: One or more recipient addresses.
        subject: Email subject line.
        html: HTML body.
        text: Optional plain-text alternative.

    Returns:
        ``EmailResult`` indicating success or failure.  Never raises.
    """
    recipients = [to] if isinstance(to, str) else to

    if not settings.EMAIL_PROVIDER_API_KEY:
        # Console fallback — log a summary and return.
        logger.info(
            "email_console_fallback",
            to=recipients,
            subject=subject,
            html_length=len(html),
        )
        return EmailResult(success=True, message_id="console-fallback")

    payload: dict[str, object] = {
        "from": settings.EMAIL_FROM_ADDRESS,
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        async with httpx.AsyncClient(timeout=_EMAIL_TIMEOUT_SECONDS) as client:
            response = await asyncio.wait_for(
                client.post(
                    _RESEND_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.EMAIL_PROVIDER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                ),
                timeout=_EMAIL_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            message_id = data.get("id", "") if isinstance(data, dict) else ""

        logger.info(
            "email_sent",
            to=recipients,
            subject=subject,
            message_id=message_id,
        )
        return EmailResult(success=True, message_id=message_id)

    except httpx.HTTPStatusError as exc:
        error_body = _extract_error_body(exc)
        logger.error(
            "email_send_failed",
            to=recipients,
            subject=subject,
            status_code=exc.response.status_code,
            error=error_body,
        )
        return EmailResult(
            success=False,
            error=f"HTTP {exc.response.status_code}: {error_body}",
        )

    except (httpx.HTTPError, TimeoutError) as exc:
        logger.error(
            "email_send_failed",
            to=recipients,
            subject=subject,
            error=str(exc),
        )
        return EmailResult(success=False, error=str(exc))


# ── HTML template helpers ─────────────────────────────────────────────────────


def _verification_html(name: str, verify_url: str) -> str:  # noqa: E501
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:24px">
  <div style="max-width:480px;margin:0 auto">
    <h1 style="font-size:20px;margin-bottom:16px">Verify your email</h1>
    <p style="font-size:14px;line-height:1.6;color:#333">Hi {name},</p>
    <p style="font-size:14px;line-height:1.6;color:#333">Thanks for signing up! Please verify your email address by clicking the button below:</p>
    <a href="{verify_url}" style="display:inline-block;padding:12px 24px;background-color:#0066FF;color:white;text-decoration:none;border-radius:6px;font-size:14px;margin:16px 0">Verify Email</a>
    <p style="font-size:12px;line-height:1.5;color:#888">Or copy this link:<br><a href="{verify_url}" style="color:#0066FF">{verify_url}</a></p>
    <p style="font-size:12px;line-height:1.5;color:#888">This link expires in 24 hours. If you did not create an account, ignore this email.</p>
  </div>
</body>
</html>"""


def _password_reset_html(name: str, reset_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:24px">
  <div style="max-width:480px;margin:0 auto">
    <h1 style="font-size:20px;margin-bottom:16px">Reset your password</h1>
    <p style="font-size:14px;line-height:1.6;color:#333">Hi {name},</p>
    <p style="font-size:14px;line-height:1.6;color:#333">We received a request to reset your password. Click the button below to set a new one:</p>
    <a href="{reset_url}" style="display:inline-block;padding:12px 24px;background-color:#0066FF;color:white;text-decoration:none;border-radius:6px;font-size:14px;margin:16px 0">Reset Password</a>
    <p style="font-size:12px;line-height:1.5;color:#888">Or copy this link:<br><a href="{reset_url}" style="color:#0066FF">{reset_url}</a></p>
    <p style="font-size:12px;line-height:1.5;color:#888">This link expires in 1 hour. If you did not request this, ignore this email.</p>
  </div>
</body>
</html>"""


def _team_invitation_html(team_name: str, inviter_name: str, accept_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:24px">
  <div style="max-width:480px;margin:0 auto">
    <h1 style="font-size:20px;margin-bottom:16px">You're invited!</h1>
    <p style="font-size:14px;line-height:1.6;color:#333"><strong>{inviter_name}</strong> has invited you to join <strong>{team_name}</strong> on MCPForge.</p>
    <a href="{accept_url}" style="display:inline-block;padding:12px 24px;background-color:#0066FF;color:white;text-decoration:none;border-radius:6px;font-size:14px;margin:16px 0">Accept Invitation</a>
    <p style="font-size:12px;line-height:1.5;color:#888">This invitation expires in 48 hours.</p>
  </div>
</body>
</html>"""


# ── High-level send helpers ───────────────────────────────────────────────────


async def send_verification_email(
    email: str,
    display_name: str,
    token: str,
    base_url: str,
) -> EmailResult:
    """Send an email-verification message.

    Args:
        email: Recipient address.
        display_name: User's display name (or empty string).
        token: Signed JWT token for the verification link.
        base_url: Application base URL (e.g. ``https://app.mcpforge.io``).
    """
    name = display_name or email.split("@")[0]
    verify_url = f"{base_url.rstrip('/')}/verify-email?token={token}"
    html = _verification_html(name, verify_url)
    text = (
        f"Hi {name},\n\n"
        f"Please verify your email by visiting:\n{verify_url}\n\n"
        f"This link expires in 24 hours."
    )
    return await send_email(
        to=email,
        subject="Verify your email — MCPForge",
        html=html,
        text=text,
    )


async def send_password_reset_email(
    email: str,
    display_name: str,
    token: str,
    base_url: str,
) -> EmailResult:
    """Send a password-reset message.

    Args:
        email: Recipient address.
        display_name: User's display name (or empty string).
        token: Signed JWT token for the reset link.
        base_url: Application base URL.
    """
    name = display_name or email.split("@")[0]
    reset_url = f"{base_url.rstrip('/')}/reset-password?token={token}"
    html = _password_reset_html(name, reset_url)
    text = (
        f"Hi {name},\n\n"
        f"Reset your password by visiting:\n{reset_url}\n\n"
        f"This link expires in 1 hour."
    )
    return await send_email(
        to=email,
        subject="Reset your password — MCPForge",
        html=html,
        text=text,
    )


async def send_team_invitation_email(
    email: str,
    team_name: str,
    inviter_name: str,
    token: str,
    base_url: str,
) -> EmailResult:
    """Send a team-invitation message.

    Args:
        email: Recipient address.
        team_name: Name of the inviting team.
        inviter_name: Name of the person who sent the invitation.
        token: Invitation token.
        base_url: Application base URL.
    """
    accept_url = f"{base_url.rstrip('/')}/dashboard/team/accept?token={token}"
    html = _team_invitation_html(team_name, inviter_name, accept_url)
    text = (
        f"{inviter_name} has invited you to join {team_name} on MCPForge.\n\n"
        f"Accept: {accept_url}"
    )
    return await send_email(
        to=email,
        subject=f"You've been invited to {team_name} — MCPForge",
        html=html,
        text=text,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _extract_error_body(exc: httpx.HTTPStatusError) -> str:
    """Safely extract a short error description from an HTTP error response."""
    try:
        body = exc.response.json()
        if isinstance(body, dict):
            return str(body.get("message") or body.get("error") or body)[:200]
        return str(body)[:200]
    except Exception:
        return (exc.response.text or "")[:200]
