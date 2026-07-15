import hashlib
import secrets
import uuid
from dataclasses import dataclass

from app.application.protocols import AgentTokenRepository, FirewallRepository, UnitOfWork
from app.domain.entities import AgentToken
from app.domain.errors import FirewallNotFoundError


@dataclass(frozen=True)
class RotateTokenRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID


@dataclass(frozen=True)
class RotateTokenResult:
    agent_token: str


class RotateToken:
    def __init__(
        self,
        firewalls: FirewallRepository,
        agent_tokens: AgentTokenRepository,
        uow: UnitOfWork,
    ) -> None:
        self._firewalls = firewalls
        self._agent_tokens = agent_tokens
        self._uow = uow

    async def execute(self, request: RotateTokenRequest) -> RotateTokenResult:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        await self._agent_tokens.revoke_all_for_firewall(fw.id)

        plain_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
        token = AgentToken(firewall_id=fw.id, token_hash=token_hash)
        await self._agent_tokens.create(token)

        await self._uow.commit()
        return RotateTokenResult(agent_token=plain_token)
