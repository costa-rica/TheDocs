import smtplib
from email.message import EmailMessage
from typing import Optional

from loguru import logger


def send_verification_email(
    smtp_host: Optional[str],
    smtp_port: Optional[int],
    smtp_user: Optional[str],
    smtp_password: Optional[str],
    to_email: str,
    verification_url: str,
) -> bool:
    if not smtp_host or not smtp_port or not smtp_user or not smtp_password:
        logger.error("SMTP configuration missing; cannot send verification email")
        return False

    message = EmailMessage()
    message["Subject"] = "Your TheDocs login link"
    message["From"] = smtp_user
    message["To"] = to_email
    message.set_content(
        "Use the link below to complete your login:\n\n"
        f"{verification_url}\n\n"
        "This link expires shortly. If you did not request it, ignore this email."
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        return True
    except Exception as exc:  # pragma: no cover - network
        logger.error(f"Failed to send verification email: {exc}")
        return False
