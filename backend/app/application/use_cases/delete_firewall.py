import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.protocols import AgentTokenRepository, FirewallRepository, UnitOfWork
from app.domain.errors import FirewallNotFoundError


@dataclass(frozen=True)
class DeleteFirewallRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID


class DeleteFirewall:
    def __init__(
        self,
        firewalls: FirewallRepository,
        agent_tokens: AgentTokenRepository,
        uow: UnitOfWork,
    ) -> None:
        self._firewalls = firewalls
        self._agent_tokens = agent_tokens
        self._uow = uow

    async def execute(self, request: DeleteFirewallRequest) -> None:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        await self._agent_tokens.revoke_all_for_firewall(fw.id)

        fw.deleted_at = datetime.now(UTC)
        await self._firewalls.update(fw)
        await self._uow.commit()
