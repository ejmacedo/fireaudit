import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.protocols import (
    FirewallCommandRepository,
    FirewallRepository,
    PasswordVerifier,
    UnitOfWork,
    UserRepository,
)
from app.domain.entities import FirewallCommand
from app.domain.errors import (
    FirewallCommandExpiredError,
    FirewallCommandNotFoundError,
    FirewallCommandNotPendingError,
    FirewallNotFoundError,
    InvalidCredentialsError,
)


@dataclass(frozen=True)
class ConfirmFirewallCommandRequest:
    firewall_id: uuid.UUID
    command_id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    password: str


class ConfirmFirewallCommand:
    """Step-up authentication for a pending remote write: re-verifies the user's current
    password before moving the command from 'pending_confirmation' to 'confirmed'.

    Confirmation does not itself dispatch to the agent — the agent's own poll picks up
    'confirmed' commands and transitions them to 'sent_to_agent' (agent always initiates,
    per the Push+Poll architecture)."""

    def __init__(
        self,
        firewalls: FirewallRepository,
        firewall_commands: FirewallCommandRepository,
        users: UserRepository,
        verifier: PasswordVerifier,
        uow: UnitOfWork,
    ) -> None:
        self._firewalls = firewalls
        self._firewall_commands = firewall_commands
        self._users = users
        self._verifier = verifier
        self._uow = uow

    async def execute(self, request: ConfirmFirewallCommandRequest) -> FirewallCommand:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        command = await self._firewall_commands.get_by_id(request.command_id)
        if command is None or command.firewall_id != fw.id:
            raise FirewallCommandNotFoundError

        if command.status != "pending_confirmation":
            raise FirewallCommandNotPendingError

        now = datetime.now(UTC)
        expires_at = command.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < now:
            await self._firewall_commands.update_status(command.id, status="expired")
            await self._uow.commit()
            raise FirewallCommandExpiredError

        user = await self._users.get_by_id(request.user_id)
        if user is None or not self._verifier.verify(request.password, user.password_hash):
            raise InvalidCredentialsError

        confirmed = await self._firewall_commands.update_status(
            command.id, status="confirmed", confirmed_at=now
        )
        await self._uow.commit()
        return confirmed
