import hashlib
import secrets
import uuid
from dataclasses import dataclass

from app.application.protocols import AgentTokenRepository, FirewallRepository, UnitOfWork
from app.domain.entities import AgentToken, Firewall
from app.domain.errors import FirewallNameEmptyError


@dataclass(frozen=True)
class CreateFirewallRequest:
    organization_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class CreateFirewallResult:
    firewall: Firewall
    agent_token: str


class CreateFirewall:
    def __init__(
        self,
        firewalls: FirewallRepository,
        agent_tokens: AgentTokenRepository,
        uow: UnitOfWork,
    ) -> None:
        self._firewalls = firewalls
        self._agent_tokens = agent_tokens
        self._uow = uow

    async def execute(self, request: CreateFirewallRequest) -> CreateFirewallResult:
        name = request.name.strip()
        if not name:
            raise FirewallNameEmptyError

        firewall = Firewall(organization_id=request.organization_id, name=name)
        firewall = await self._firewalls.create(firewall)

        plain_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
        token = AgentToken(firewall_id=firewall.id, token_hash=token_hash)
        await self._agent_tokens.create(token)

        await self._uow.commit()
        return CreateFirewallResult(firewall=firewall, agent_token=plain_token)
