from dataclasses import dataclass

from app.application.protocols import (
    RefreshTokenRepository,
    TokenService,
    UnitOfWork,
)


@dataclass(frozen=True)
class LogoutRequest:
    refresh_token: str


class LogoutUser:
    def __init__(
        self,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        uow: UnitOfWork,
    ) -> None:
        self._refresh_tokens = refresh_tokens
        self._tokens = tokens
        self._uow = uow

    async def execute(self, request: LogoutRequest) -> None:
        token_hash = self._tokens.hash_refresh_token(request.refresh_token)
        token = await self._refresh_tokens.get_by_token_hash(token_hash)
        if token is None or token.revoked_at is not None:
            # Idempotent: logging out an unknown/already-revoked token is a no-op.
            return
        await self._refresh_tokens.revoke(token.id)
        await self._uow.commit()
