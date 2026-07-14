import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Account, Organization, User
from app.domain.errors import InvalidRefreshTokenError
from app.infrastructure.database import get_db
from app.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.security import build_token_service


@dataclass(frozen=True)
class AuthContext:
    user: User
    account: Account
    organizations: list[Organization]

    @property
    def organization_ids(self) -> set[uuid.UUID]:
        return {org.id for org in self.organizations}


def _extract_bearer(request: Request) -> str:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTH_REQUIRED", "message": "Missing authorization header."}},
        )
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Malformed authorization header.",
                }
            },
        )
    return token


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> AuthContext:
    token = _extract_bearer(request)
    tokens = build_token_service()
    try:
        claims = tokens.decode_access_token(token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Access token is invalid or expired.",
                }
            },
        ) from exc

    users_repo = SqlAlchemyUserRepository(session)
    accounts_repo = SqlAlchemyAccountRepository(session)
    orgs_repo = SqlAlchemyOrganizationRepository(session)

    user = await users_repo.get_by_id(claims.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "User not found."}},
        )
    account = await accounts_repo.get_by_id(user.account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Account not found."}},
        )
    orgs = await orgs_repo.list_active_for_account(account.id)

    return AuthContext(user=user, account=account, organizations=orgs)
