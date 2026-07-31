from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.protocols import (
    PasswordHasher,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    TokenService,
    UnitOfWork,
    UserRepository,
)
from app.domain.errors import InvalidOrExpiredResetTokenError


@dataclass(frozen=True)
class ResetPasswordRequest:
    token: str
    new_password: str


class ResetPassword:
    def __init__(
        self,
        users: UserRepository,
        reset_tokens: PasswordResetTokenRepository,
        refresh_tokens: RefreshTokenRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        uow: UnitOfWork,
    ) -> None:
        self._users = users
        self._reset_tokens = reset_tokens
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._tokens = tokens
        self._uow = uow

    async def execute(self, request: ResetPasswordRequest) -> None:
        token_hash = self._tokens.hash_refresh_token(request.token)
        reset_token = await self._reset_tokens.get_by_token_hash(token_hash)
        if reset_token is None:
            raise InvalidOrExpiredResetTokenError()
        if reset_token.used_at is not None:
            raise InvalidOrExpiredResetTokenError()
        if reset_token.expires_at <= datetime.now(UTC):
            raise InvalidOrExpiredResetTokenError()

        user = await self._users.get_by_id(reset_token.user_id)
        if user is None:
            raise InvalidOrExpiredResetTokenError()

        await self._reset_tokens.mark_used(reset_token.id)
        new_hash = self._hasher.hash(request.new_password)
        await self._users.update_password_hash(user.id, new_hash)
        await self._refresh_tokens.revoke_all_for_user(user.id)
        await self._uow.commit()
