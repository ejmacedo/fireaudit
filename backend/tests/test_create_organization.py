"""Phase 2 unit test: individual/1-org invariant enforced in the application layer."""

import uuid

import pytest

from app.application.use_cases.create_organization import (
    CreateOrganization,
    CreateOrganizationRequest,
)
from app.domain.entities import Account, Organization
from app.domain.errors import IndividualAccountAlreadyHasOrganizationError


class FakeAccountRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, Account] = {}

    def _seed(self, account: Account) -> None:
        self._items[account.id] = account

    async def create(self, account: Account) -> Account:
        self._items[account.id] = account
        return account

    async def get_by_id(self, account_id: uuid.UUID) -> Account | None:
        return self._items.get(account_id)


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, Organization] = {}

    async def create(self, organization: Organization) -> Organization:
        self._items[organization.id] = organization
        return organization

    async def count_active_for_account(self, account_id: uuid.UUID) -> int:
        return sum(
            1
            for org in self._items.values()
            if org.account_id == account_id and org.deleted_at is None
        )


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None: ...


async def test_individual_account_accepts_first_organization():
    accounts = FakeAccountRepository()
    organizations = FakeOrganizationRepository()
    uow = FakeUnitOfWork()
    account = Account(account_type="individual")
    accounts._seed(account)

    use_case = CreateOrganization(accounts, organizations, uow)
    result = await use_case.execute(CreateOrganizationRequest(account_id=account.id, name="Acme"))

    assert result.name == "Acme"
    assert result.account_id == account.id
    assert uow.commits == 1


async def test_individual_account_rejects_second_organization():
    accounts = FakeAccountRepository()
    organizations = FakeOrganizationRepository()
    uow = FakeUnitOfWork()
    account = Account(account_type="individual")
    accounts._seed(account)
    await organizations.create(Organization(account_id=account.id, name="First"))

    use_case = CreateOrganization(accounts, organizations, uow)

    with pytest.raises(IndividualAccountAlreadyHasOrganizationError):
        await use_case.execute(CreateOrganizationRequest(account_id=account.id, name="Second"))
    assert uow.commits == 0


async def test_multiempresa_account_accepts_second_organization():
    accounts = FakeAccountRepository()
    organizations = FakeOrganizationRepository()
    uow = FakeUnitOfWork()
    account = Account(account_type="multiempresa", tax_id="12345")
    accounts._seed(account)
    await organizations.create(Organization(account_id=account.id, name="First"))

    use_case = CreateOrganization(accounts, organizations, uow)
    result = await use_case.execute(CreateOrganizationRequest(account_id=account.id, name="Second"))

    assert result.name == "Second"
    assert uow.commits == 1
