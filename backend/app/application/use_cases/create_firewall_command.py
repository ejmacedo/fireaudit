import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.protocols import FirewallCommandRepository, FirewallRepository, UnitOfWork
from app.domain.entities import FirewallCommand
from app.domain.errors import FirewallNotFoundError, InvalidFirewallCommandTypeError

ALLOWED_COMMAND_TYPES = frozenset({"create_rule", "update_rule", "delete_rule"})


@dataclass(frozen=True)
class CreateFirewallCommandRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    command_type: str
    payload: dict


class CreateFirewallCommand:
    """Queues a remote write for explicit user confirmation (Pilar 4 — Gerenciamento Remoto).

    The command starts in 'pending_confirmation' — nothing is sent to the agent until
    ConfirmFirewallCommand verifies step-up authentication (password reauth) and
    moves it to 'sent_to_agent'.
    """

    def __init__(
        self,
        firewalls: FirewallRepository,
        firewall_commands: FirewallCommandRepository,
        uow: UnitOfWork,
        ttl_minutes: int,
    ) -> None:
        self._firewalls = firewalls
        self._firewall_commands = firewall_commands
        self._uow = uow
        self._ttl_minutes = ttl_minutes

    async def execute(self, request: CreateFirewallCommandRequest) -> FirewallCommand:
        if request.command_type not in ALLOWED_COMMAND_TYPES:
            raise InvalidFirewallCommandTypeError

        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        expires_at = datetime.now(UTC) + timedelta(minutes=self._ttl_minutes)
        command = FirewallCommand(
            firewall_id=fw.id,
            user_id=request.user_id,
            command_type=request.command_type,
            payload=request.payload,
            preview=dict(request.payload),
            expires_at=expires_at,
        )
        command = await self._firewall_commands.create(command)
        await self._uow.commit()
        return command
