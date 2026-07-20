import uuid
from dataclasses import dataclass

from app.application.protocols import FirewallRepository, SnapshotRepository
from app.domain.errors import FirewallNotFoundError


@dataclass(frozen=True)
class GetFirewallRulesRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID


class GetFirewallRules:
    def __init__(self, firewalls: FirewallRepository, snapshots: SnapshotRepository) -> None:
        self._firewalls = firewalls
        self._snapshots = snapshots

    async def execute(self, request: GetFirewallRulesRequest) -> list[dict]:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        snapshot = await self._snapshots.get_latest_for_firewall(request.firewall_id)
        if snapshot is None:
            return []
        return snapshot.raw_payload.get("rules", []) or []
