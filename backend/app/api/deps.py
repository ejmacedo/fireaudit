from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.logout_user import LogoutUser
from app.application.use_cases.refresh_session import RefreshSession
from app.application.use_cases.register_account import (
    RegisterIndividualAccount,
    RegisterMultiempresaAccount,
)
from app.core.config import settings
from app.infrastructure.database import get_db
from app.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUnitOfWork,
    SqlAlchemyUserRepository,
)
from app.infrastructure.security import (
    Argon2PasswordHasher,
    Argon2PasswordVerifier,
    build_token_service,
)


def get_register_individual(
    session: AsyncSession = Depends(get_db),
) -> RegisterIndividualAccount:
    return RegisterIndividualAccount(
        accounts=SqlAlchemyAccountRepository(session),
        organizations=SqlAlchemyOrganizationRepository(session),
        users=SqlAlchemyUserRepository(session),
        hasher=Argon2PasswordHasher(),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_register_multiempresa(
    session: AsyncSession = Depends(get_db),
) -> RegisterMultiempresaAccount:
    return RegisterMultiempresaAccount(
        accounts=SqlAlchemyAccountRepository(session),
        users=SqlAlchemyUserRepository(session),
        hasher=Argon2PasswordHasher(),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_login_user(session: AsyncSession = Depends(get_db)) -> LoginUser:
    return LoginUser(
        users=SqlAlchemyUserRepository(session),
        refresh_tokens=SqlAlchemyRefreshTokenRepository(session),
        verifier=Argon2PasswordVerifier(),
        tokens=build_token_service(),
        uow=SqlAlchemyUnitOfWork(session),
        access_token_ttl_minutes=settings.jwt_access_token_expire_minutes,
        refresh_token_ttl_days=settings.jwt_refresh_token_expire_days,
    )


def get_refresh_session(session: AsyncSession = Depends(get_db)) -> RefreshSession:
    return RefreshSession(
        users=SqlAlchemyUserRepository(session),
        refresh_tokens=SqlAlchemyRefreshTokenRepository(session),
        tokens=build_token_service(),
        uow=SqlAlchemyUnitOfWork(session),
        access_token_ttl_minutes=settings.jwt_access_token_expire_minutes,
        refresh_token_ttl_days=settings.jwt_refresh_token_expire_days,
    )


def get_logout_user(session: AsyncSession = Depends(get_db)) -> LogoutUser:
    return LogoutUser(
        refresh_tokens=SqlAlchemyRefreshTokenRepository(session),
        tokens=build_token_service(),
        uow=SqlAlchemyUnitOfWork(session),
    )
