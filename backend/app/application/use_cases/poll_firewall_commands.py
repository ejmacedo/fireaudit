import uuid
from dataclasses import dataclass

from app.application.protocols import FirewallCommandRepository
from app.domain.entities import FirewallCommand


@dataclass(frozen=True)
class PollFirewallCommandsRequest:
    firewall_id: uuid.UUID


class PollFirewallCommands:
    """Agent-facing: returns commands the user has confirmed and moves them to
    'sent_to_agent'. The agent always initiates (push snapshot + poll commands) —
    the backend never connects directly to the firewall."""

    def __init__(self, firewall_commands: FirewallCommandRepository) -> None:
        self._firewall_commands = firewall_commands

    async def execute(self, request: PollFirewallCommandsRequest) -> list[FirewallCommand]:
        all_commands = await self._firewall_commands.list_for_firewall(request.firewall_id)
        confirmed = [c for c in all_commands if c.status == "confirmed"]

        dispatched = []
        for command in confirmed:
            updated = await self._firewall_commands.update_status(
                command.id, status="sent_to_agent"
            )
            dispatched.append(updated)
        return dispatched
