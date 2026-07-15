import uuid
from dataclasses import dataclass

from app.application.protocols import FirewallRepository
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


class ListFirewalls:
    def __init__(self, firewalls: FirewallRepository) -> None:
        self._firewalls = firewalls

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
        return ListFirewallsResult(firewalls=page, next_cursor=next_cursor)
