from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.register_account import (
    RegisterIndividualAccount,
    RegisterMultiempresaAccount,
)
from app.infrastructure.database import get_db
from app.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyUnitOfWork,
    SqlAlchemyUserRepository,
)
from app.infrastructure.security import Argon2PasswordHasher


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
