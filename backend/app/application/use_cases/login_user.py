from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.protocols import (
    PasswordVerifier,
    RefreshTokenRepository,
    TokenService,
    UnitOfWork,
    UserRepository,
)
from app.domain.entities import RefreshToken
from app.domain.errors import InvalidCredentialsError


@dataclass(frozen=True)
class LoginRequest:
    email: str
    password: str


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    refresh_token: str
    access_token_expires_in_seconds: int


class LoginUser:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        verifier: PasswordVerifier,
        tokens: TokenService,
        uow: UnitOfWork,
        access_token_ttl_minutes: int,
        refresh_token_ttl_days: int,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._verifier = verifier
        self._tokens = tokens
        self._uow = uow
        self._access_ttl_min = access_token_ttl_minutes
        self._refresh_ttl_days = refresh_token_ttl_days

    async def execute(self, request: LoginRequest) -> LoginResult:
        user = await self._users.get_by_email(request.email)
        if user is None or not self._verifier.verify(request.password, user.password_hash):
            raise InvalidCredentialsError()

        access_token = self._tokens.create_access_token(user.id, user.account_id)
        refresh_plain = self._tokens.generate_refresh_token()
        refresh_hash = self._tokens.hash_refresh_token(refresh_plain)
        expires_at = datetime.now(UTC) + timedelta(days=self._refresh_ttl_days)
        await self._refresh_tokens.create(
            RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=expires_at)
        )
        await self._uow.commit()

        return LoginResult(
            access_token=access_token,
            refresh_token=refresh_plain,
            access_token_expires_in_seconds=self._access_ttl_min * 60,
        )
