import uuid
from dataclasses import dataclass

from app.application.protocols import (
    AccountRepository,
    OrganizationRepository,
    PasswordHasher,
    UnitOfWork,
    UserRepository,
)
from app.domain.entities import Account, Organization, User
from app.domain.errors import EmailAlreadyRegisteredError


@dataclass(frozen=True)
class RegisterIndividualRequest:
    email: str
    password: str
    organization_name: str


@dataclass(frozen=True)
class RegisterMultiempresaRequest:
    email: str
    password: str
    tax_id: str


@dataclass(frozen=True)
class RegisterResult:
    account_id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID | None


class RegisterIndividualAccount:
    def __init__(
        self,
        accounts: AccountRepository,
        organizations: OrganizationRepository,
        users: UserRepository,
        hasher: PasswordHasher,
        uow: UnitOfWork,
    ) -> None:
        self._accounts = accounts
        self._organizations = organizations
        self._users = users
        self._hasher = hasher
        self._uow = uow

    async def execute(self, request: RegisterIndividualRequest) -> RegisterResult:
        if await self._users.get_by_email(request.email) is not None:
            raise EmailAlreadyRegisteredError(request.email)

        account = await self._accounts.create(Account(account_type="individual"))
        organization = await self._organizations.create(
            Organization(account_id=account.id, name=request.organization_name)
        )
        user = await self._users.create(
            User(
                account_id=account.id,
                email=request.email,
                password_hash=self._hasher.hash(request.password),
            )
        )
        await self._uow.commit()
        return RegisterResult(
            account_id=account.id,
            user_id=user.id,
            organization_id=organization.id,
        )


class RegisterMultiempresaAccount:
    def __init__(
        self,
        accounts: AccountRepository,
        users: UserRepository,
        hasher: PasswordHasher,
        uow: UnitOfWork,
    ) -> None:
        self._accounts = accounts
        self._users = users
        self._hasher = hasher
        self._uow = uow

    async def execute(self, request: RegisterMultiempresaRequest) -> RegisterResult:
        if await self._users.get_by_email(request.email) is not None:
            raise EmailAlreadyRegisteredError(request.email)

        account = await self._accounts.create(
            Account(account_type="multiempresa", tax_id=request.tax_id)
        )
        user = await self._users.create(
            User(
                account_id=account.id,
                email=request.email,
                password_hash=self._hasher.hash(request.password),
            )
        )
        await self._uow.commit()
        return RegisterResult(
            account_id=account.id,
            user_id=user.id,
            organization_id=None,
        )
