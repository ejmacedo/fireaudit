import uuid
from dataclasses import dataclass

from app.application.protocols import FirewallRepository, UnitOfWork
from app.domain.entities import Firewall
from app.domain.errors import FirewallNameEmptyError, FirewallNotFoundError


@dataclass(frozen=True)
class RenameFirewallRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID
    name: str


class RenameFirewall:
    def __init__(self, firewalls: FirewallRepository, uow: UnitOfWork) -> None:
        self._firewalls = firewalls
        self._uow = uow

    async def execute(self, request: RenameFirewallRequest) -> Firewall:
        name = request.name.strip()
        if not name:
            raise FirewallNameEmptyError

        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        fw.name = name
        fw = await self._firewalls.update(fw)
        await self._uow.commit()
        return fw
