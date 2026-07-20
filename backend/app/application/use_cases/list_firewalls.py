import uuid
from dataclasses import dataclass, field

from app.application.protocols import FindingRepository, FirewallRepository
from app.domain.entities import Firewall


@dataclass(frozen=True)
class ListFirewallsRequest:
    organization_id: uuid.UUID
    cursor: uuid.UUID | None
    limit: int


@dataclass(frozen=True)
class ListFirewallsResult:
    firewalls: list[Firewall]
    next_cursor: uuid.UUID | None
    open_findings_by_severity: dict[uuid.UUID, dict[str, int]] = field(default_factory=dict)


class ListFirewalls:
    def __init__(self, firewalls: FirewallRepository, findings: FindingRepository) -> None:
        self._firewalls = firewalls
        self._findings = findings

    async def execute(self, request: ListFirewallsRequest) -> ListFirewallsResult:
        limit = min(max(request.limit, 1), 100)
        rows = await self._firewalls.list_active_for_org(
            organization_id=request.organization_id,
            cursor=request.cursor,
            limit=limit + 1,
        )
        has_next = len(rows) > limit
        page = rows[:limit]
        next_cursor = page[-1].id if has_next else None
        counts = await self._findings.count_open_grouped_by_severity([fw.id for fw in page])
        return ListFirewallsResult(
            firewalls=page, next_cursor=next_cursor, open_findings_by_severity=counts
        )
