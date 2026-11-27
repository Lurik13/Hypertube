"""Outgoing email over SMTP (Mailpit in dev)."""

import html
import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, text: str, html_body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html_body, subtype="html")
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password.get_secret_value() or None,
            start_tls=settings.smtp_starttls,
            timeout=10,
        )
    except (aiosmtplib.SMTPException, OSError) as exc:
        # Never log the message itself: it contains a reset link.
        logger.error("Could not send email %r: %s", subject, type(exc).__name__)


async def send_password_reset_email(to: str, first_name: str, link: str) -> None:
    minutes = get_settings().password_reset_ttl_minutes
    greeting = f"Hello {first_name}," if first_name else "Hello,"
    text = (
        f"{greeting}\n\n"
        f"Someone asked to reset the password of your Hypertube account.\n"
        f"Open this link to choose a new one (valid {minutes} minutes, single use):\n\n"
        f"{link}\n\n"
        f"If it wasn't you, ignore this email: your password stays the same.\n"
    )
    html_body = (
        f"<p>{html.escape(greeting)}</p>"
        f"<p>Someone asked to reset the password of your Hypertube account.</p>"
        f'<p><a href="{html.escape(link)}">Choose a new password</a> '
        f"(valid {minutes} minutes, single use).</p>"
        f"<p>If it wasn't you, ignore this email: your password stays the same.</p>"
    )
    await send_email(to, "Reset your Hypertube password", text, html_body)
