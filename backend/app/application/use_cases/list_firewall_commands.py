import uuid
from dataclasses import dataclass

from app.application.protocols import FirewallCommandRepository, FirewallRepository
from app.domain.entities import FirewallCommand
from app.domain.errors import FirewallNotFoundError


@dataclass(frozen=True)
class ListFirewallCommandsRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID


class ListFirewallCommands:
    def __init__(
        self,
        firewalls: FirewallRepository,
        firewall_commands: FirewallCommandRepository,
    ) -> None:
        self._firewalls = firewalls
        self._firewall_commands = firewall_commands

    async def execute(self, request: ListFirewallCommandsRequest) -> list[FirewallCommand]:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError
        return await self._firewall_commands.list_for_firewall(fw.id)
