"""
services/email_service.py

Configurable SMTP email delivery service for AI Coding Assistant.
Handles password reset emails with both plain-text and HTML formatting.
Adheres strictly to credential protection: passwords and tokens are never logged.
"""
from __future__ import annotations

import email.mime.multipart
import email.mime.text
import smtplib
import ssl
from typing import Optional, Tuple

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """
    Service responsible for dispatching system emails via configurable SMTP.
    Supports STARTTLS, SSL (port 465), and authenticated SMTP accounts (e.g. Gmail App Password).
    """

    def __init__(self) -> None:
        pass

    @property
    def is_configured(self) -> bool:
        """Return True if SMTP host is configured and non-empty."""
        return bool(settings.smtp_host and settings.smtp_host.strip())

    def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_link: str,
        expiry_minutes: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Send a password reset email containing the secure single-use link.

        Returns:
            Tuple of (success: bool, status_message: str)
        """
        if not to_email or "@" not in to_email:
            return False, "Invalid recipient email address."

        if not self.is_configured:
            logger.info("SMTP host is not configured; email dispatch skipped.")
            return False, "SMTP service is not configured."

        expiry = expiry_minutes or settings.password_reset_token_expiry_minutes
        display_name = user_name.strip() if user_name else "Developer"

        subject = "Reset your AI Coding Assistant password"
        from_email = (
            settings.smtp_from_email.strip()
            or settings.smtp_username.strip()
            or "no-reply@aicodingassistant.local"
        )

        # Plain text fallback body
        text_body = (
            f"Hello {display_name},\n\n"
            f"A password reset was requested for your account.\n\n"
            f"Use the secure reset link below:\n"
            f"{reset_link}\n\n"
            f"This link expires after {expiry} minutes and can only be used once.\n\n"
            f"If you did not request this, you can safely ignore this email.\n\n"
            f"Regards,\n"
            f"AI Coding Assistant\n"
        )

        # Polished HTML body
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0e1117; color: #e6edf3; padding: 24px; }}
    .container {{ max-width: 560px; margin: 0 auto; background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 32px; }}
    .header {{ text-align: center; border-bottom: 1px solid #30363d; padding-bottom: 20px; margin-bottom: 24px; }}
    .header h1 {{ color: #58a6ff; font-size: 22px; margin: 0; }}
    .button {{ display: inline-block; background-color: #238636; color: #ffffff !important; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
    .footer {{ font-size: 12px; color: #8b949e; margin-top: 32px; border-top: 1px solid #30363d; padding-top: 16px; }}
    .link-alt {{ word-break: break-all; color: #58a6ff; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🤖 AI Coding Assistant</h1>
    </div>
    <p>Hello <strong>{display_name}</strong>,</p>
    <p>A password reset was requested for your account.</p>
    <p style="text-align: center;">
      <a href="{reset_link}" class="button" target="_blank">Reset Your Password</a>
    </p>
    <p>Or copy and paste this link into your browser:</p>
    <p class="link-alt">{reset_link}</p>
    <p>This link expires in <strong>{expiry} minutes</strong> and can only be used once.</p>
    <p>If you did not request a password reset, you can safely ignore this email.</p>
    <div class="footer">
      Regards,<br>
      <strong>AI Coding Assistant Team</strong>
    </div>
  </div>
</body>
</html>
"""

        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        part_text = email.mime.text.MIMEText(text_body, "plain", "utf-8")
        part_html = email.mime.text.MIMEText(html_body, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        try:
            port = int(settings.smtp_port)
            host = settings.smtp_host.strip()

            if port == 465:
                # SSL connection
                ssl_context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, context=ssl_context, timeout=10) as server:
                    if settings.smtp_username and settings.smtp_password:
                        server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(msg)
            else:
                # Plain / STARTTLS connection
                with smtplib.SMTP(host, port, timeout=10) as server:
                    if settings.smtp_use_tls:
                        ssl_context = ssl.create_default_context()
                        server.starttls(context=ssl_context)
                    if settings.smtp_username and settings.smtp_password:
                        server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(msg)

            logger.info("Password reset email successfully sent to recipient.")
            return True, "Password reset email sent successfully."

        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP authentication failed during email delivery: %s", exc)
            return False, "SMTP authentication failed. Please verify mail credentials."
        except smtplib.SMTPException as exc:
            logger.error("SMTP error during email delivery: %s", exc)
            return False, "Mail server rejected password reset message."
        except Exception as exc:
            logger.error("Unexpected error delivering password reset email: %s", exc)
            return False, "Unable to deliver password reset email due to a network error."


# Singleton instance
email_service = EmailService()
