import uuid
from dataclasses import dataclass

from app.application.protocols import FirewallRepository
from app.domain.entities import Firewall
from app.domain.errors import FirewallNotFoundError


@dataclass(frozen=True)
class GetFirewallRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID


class GetFirewall:
    def __init__(self, firewalls: FirewallRepository) -> None:
        self._firewalls = firewalls

    async def execute(self, request: GetFirewallRequest) -> Firewall:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError
        return fw
