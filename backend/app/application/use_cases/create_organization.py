import uuid
from dataclasses import dataclass

from app.application.protocols import (
    AccountRepository,
    OrganizationRepository,
    UnitOfWork,
)
from app.domain.entities import Organization
from app.domain.errors import IndividualAccountAlreadyHasOrganizationError


@dataclass(frozen=True)
class CreateOrganizationRequest:
    account_id: uuid.UUID
    name: str


class CreateOrganization:
    """Only place in the system where the individual/1-org limit is enforced."""

    def __init__(
        self,
        accounts: AccountRepository,
        organizations: OrganizationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._accounts = accounts
        self._organizations = organizations
        self._uow = uow

    async def execute(self, request: CreateOrganizationRequest) -> Organization:
        account = await self._accounts.get_by_id(request.account_id)
        if account is None:
            raise ValueError(f"account {request.account_id} not found")

        if account.account_type == "individual":
            existing = await self._organizations.count_active_for_account(account.id)
            if existing >= 1:
                raise IndividualAccountAlreadyHasOrganizationError(
                    "Individual accounts are limited to exactly one organization"
                )

        organization = Organization(account_id=account.id, name=request.name)
        created = await self._organizations.create(organization)
        await self._uow.commit()
        return created
