import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.protocols import (
    FirewallCommandRepository,
    FirewallRepository,
    RemoteChangeLogRepository,
    UnitOfWork,
)
from app.domain.entities import FirewallCommand
from app.domain.errors import (
    ChangeAlreadyRolledBackError,
    FirewallNotFoundError,
    NoRemoteChangeToRollBackError,
)

ROLLBACK_COMMAND_TYPE = "rollback"


@dataclass(frozen=True)
class RollbackFirewallCommandRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID


class RollbackFirewallCommand:
    """Queues a rollback of the most recently applied remote change (Pilar 4 —
    "rollback quando tecnicamente possível").

    LIFO-only: only the single most recent RemoteChangeLog for the firewall is ever
    eligible, and only while it has not already been rolled back. This mints a new
    FirewallCommand with command_type="rollback" that flows through the SAME
    confirm (password reauth) -> agent poll -> report-result cycle as any other
    command. The generic CreateFirewallCommand/ALLOWED_COMMAND_TYPES path deliberately
    rejects "rollback" as a command_type, so only this use case may create one.
    """

    def __init__(
        self,
        firewalls: FirewallRepository,
        firewall_commands: FirewallCommandRepository,
        remote_change_logs: RemoteChangeLogRepository,
        uow: UnitOfWork,
        ttl_minutes: int,
    ) -> None:
        self._firewalls = firewalls
        self._firewall_commands = firewall_commands
        self._remote_change_logs = remote_change_logs
        self._uow = uow
        self._ttl_minutes = ttl_minutes

    async def execute(self, request: RollbackFirewallCommandRequest) -> FirewallCommand:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        latest = await self._remote_change_logs.get_latest_for_firewall(fw.id)
        if latest is None:
            raise NoRemoteChangeToRollBackError
        if latest.rolled_back_at is not None:
            raise ChangeAlreadyRolledBackError

        payload = {
            "target_change_log_id": str(latest.id),
            "restore_state": latest.before_state,
        }
        expires_at = datetime.now(UTC) + timedelta(minutes=self._ttl_minutes)
        command = FirewallCommand(
            firewall_id=fw.id,
            user_id=request.user_id,
            command_type=ROLLBACK_COMMAND_TYPE,
            payload=payload,
            preview=dict(payload),
            expires_at=expires_at,
        )
        command = await self._firewall_commands.create(command)
        await self._uow.commit()
        return command
