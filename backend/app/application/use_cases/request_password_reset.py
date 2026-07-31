import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.protocols import (
    EmailSender,
    PasswordResetTokenRepository,
    TokenService,
    UnitOfWork,
    UserRepository,
)
from app.domain.entities import PasswordResetToken

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestPasswordResetRequest:
    email: str


class RequestPasswordReset:
    """Never reveals whether the email exists — always completes silently on success."""

    def __init__(
        self,
        users: UserRepository,
        reset_tokens: PasswordResetTokenRepository,
        email_sender: EmailSender,
        tokens: TokenService,
        uow: UnitOfWork,
        token_ttl_minutes: int,
        reset_url_base: str,
    ) -> None:
        self._users = users
        self._reset_tokens = reset_tokens
        self._email_sender = email_sender
        self._tokens = tokens
        self._uow = uow
        self._ttl_minutes = token_ttl_minutes
        self._reset_url_base = reset_url_base

    async def execute(self, request: RequestPasswordResetRequest) -> None:
        user = await self._users.get_by_email(request.email)
        if user is None:
            return

        plain_token = self._tokens.generate_refresh_token()
        token_hash = self._tokens.hash_refresh_token(plain_token)
        expires_at = datetime.now(UTC) + timedelta(minutes=self._ttl_minutes)
        await self._reset_tokens.create(
            PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
        )
        await self._uow.commit()

        reset_url = f"{self._reset_url_base}?token={plain_token}"
        body_text = (
            "We received a request to reset your FireAudit password.\n\n"
            f"Reset your password using the link below (valid for {self._ttl_minutes} minutes):\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can safely ignore this email."
        )
        try:
            await self._email_sender.send(
                to=request.email,
                subject="Reset your FireAudit password",
                body_text=body_text,
            )
        except Exception:
            logger.exception("Failed to send password reset email to %s", request.email)
