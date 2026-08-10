import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.protocols import (
    FirewallCommandRepository,
    RemoteChangeLogRepository,
    UnitOfWork,
)
from app.domain.entities import RemoteChangeLog
from app.domain.errors import FirewallCommandNotAwaitingResultError, FirewallCommandNotFoundError


@dataclass(frozen=True)
class ReportFirewallCommandResultRequest:
    firewall_id: uuid.UUID
    command_id: uuid.UUID
    success: bool
    before_state: dict | None = None
    after_state: dict | None = None
    error: str | None = None


def _compute_record_hash(
    *, previous_hash: str | None, before_state: dict, after_state: dict, applied_at: datetime
) -> str:
    """SHA-256(prev_hash + before_state + after_state + applied_at) — chains each
    remote_change_logs row to the previous one for the same firewall, so tampering
    with (or deleting) any record breaks the chain for every record after it."""
    payload = {
        "previous_hash": previous_hash or "",
        "before_state": before_state,
        "after_state": after_state,
        "applied_at": applied_at.isoformat(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReportFirewallCommandResult:
    """Agent-facing: reports the outcome of applying a 'sent_to_agent' command.

    On success, appends a hash-chained RemoteChangeLog entry (registro completo /
    histórico permanente per Escopo Pilar 4) and marks the command 'applied'.
    On failure, marks the command 'failed' — no RemoteChangeLog is written since
    nothing was actually changed on the firewall.
    """

    def __init__(
        self,
        firewall_commands: FirewallCommandRepository,
        remote_change_logs: RemoteChangeLogRepository,
        uow: UnitOfWork,
    ) -> None:
        self._firewall_commands = firewall_commands
        self._remote_change_logs = remote_change_logs
        self._uow = uow

    async def execute(self, request: ReportFirewallCommandResultRequest) -> None:
        command = await self._firewall_commands.get_by_id(request.command_id)
        if command is None or command.firewall_id != request.firewall_id:
            raise FirewallCommandNotFoundError

        if command.status != "sent_to_agent":
            raise FirewallCommandNotAwaitingResultError

        now = datetime.now(UTC)

        if not request.success:
            await self._firewall_commands.update_status(command.id, status="failed")
            await self._uow.commit()
            return

        before_state = request.before_state or {}
        after_state = request.after_state or {}

        previous = await self._remote_change_logs.get_latest_for_firewall(request.firewall_id)
        record_hash = _compute_record_hash(
            previous_hash=previous.record_hash if previous else None,
            before_state=before_state,
            after_state=after_state,
            applied_at=now,
        )

        await self._remote_change_logs.create(
            RemoteChangeLog(
                firewall_command_id=command.id,
                firewall_id=command.firewall_id,
                user_id=command.user_id,
                before_state=before_state,
                after_state=after_state,
                applied_at=now,
                record_hash=record_hash,
            )
        )
        await self._firewall_commands.update_status(command.id, status="applied", applied_at=now)

        if command.command_type == "rollback":
            # This command was itself a rollback of a previous change (LIFO, Pilar 4).
            # Only now — after the agent confirms the rollback was actually applied —
            # do we mark the ORIGINAL RemoteChangeLog as rolled back. Known/accepted
            # limitation: this does not re-validate that the target is still the
            # current "latest" change at report time (agent.py remains a stub with no
            # real concurrent execution yet); hardening is deferred.
            target_id = uuid.UUID(command.payload["target_change_log_id"])
            await self._remote_change_logs.mark_rolled_back(
                target_id,
                rolled_back_by_user_id=command.user_id,
                rolled_back_at=now,
            )

        await self._uow.commit()
