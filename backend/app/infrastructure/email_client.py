import asyncio
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class SmtpEmailSender:
    """Adapter implementing app.application.protocols.EmailSender via stdlib smtplib."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email

    async def send(self, *, to: str, subject: str, body_text: str) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, body_text)

    def _send_sync(self, to: str, subject: str, body_text: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)

        with smtplib.SMTP(self._host, self._port) as smtp:
            smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)


class LoggingEmailSender:
    """No-op EmailSender used when SMTP is not configured — logs instead of sending.

    Lets the forgot-password flow be exercised end-to-end in development/tests
    without real SMTP credentials: the reset link shows up in the app logs.
    """

    async def send(self, *, to: str, subject: str, body_text: str) -> None:
        logger.info(
            "Email not sent (SMTP not configured). to=%s subject=%s\n%s",
            to,
            subject,
            body_text,
        )
