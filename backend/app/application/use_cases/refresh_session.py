from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.protocols import (
    RefreshTokenRepository,
    TokenService,
    UnitOfWork,
    UserRepository,
)
from app.application.use_cases.login_user import LoginResult
from app.domain.entities import RefreshToken
from app.domain.errors import (
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
)


@dataclass(frozen=True)
class RefreshRequest:
    refresh_token: str


class RefreshSession:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        uow: UnitOfWork,
        access_token_ttl_minutes: int,
        refresh_token_ttl_days: int,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._tokens = tokens
        self._uow = uow
        self._access_ttl_min = access_token_ttl_minutes
        self._refresh_ttl_days = refresh_token_ttl_days

    async def execute(self, request: RefreshRequest) -> LoginResult:
        current_hash = self._tokens.hash_refresh_token(request.refresh_token)
        current = await self._refresh_tokens.get_by_token_hash(current_hash)
        if current is None:
            raise InvalidRefreshTokenError()
        if current.revoked_at is not None:
            raise RefreshTokenRevokedError()
        now = datetime.now(UTC)
        if current.expires_at <= now:
            raise RefreshTokenExpiredError()

        user = await self._users.get_by_id(current.user_id)
        if user is None:
            raise InvalidRefreshTokenError()

        await self._refresh_tokens.revoke(current.id)

        access_token = self._tokens.create_access_token(user.id, user.account_id)
        new_plain = self._tokens.generate_refresh_token()
        new_hash = self._tokens.hash_refresh_token(new_plain)
        expires_at = now + timedelta(days=self._refresh_ttl_days)
        await self._refresh_tokens.create(
            RefreshToken(user_id=user.id, token_hash=new_hash, expires_at=expires_at)
        )
        await self._uow.commit()

        return LoginResult(
            access_token=access_token,
            refresh_token=new_plain,
            access_token_expires_in_seconds=self._access_ttl_min * 60,
        )
