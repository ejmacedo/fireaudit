import uuid
from dataclasses import dataclass

from app.application.protocols import FindingRepository, FirewallRepository
from app.domain.entities import Finding
from app.domain.errors import FirewallNotFoundError


@dataclass(frozen=True)
class ListFindingsRequest:
    firewall_id: uuid.UUID
    organization_id: uuid.UUID
    status: str | None = None
    severity: str | None = None
    check_type: str | None = None


class ListFindings:
    def __init__(self, firewalls: FirewallRepository, findings: FindingRepository) -> None:
        self._firewalls = firewalls
        self._findings = findings

    async def execute(self, request: ListFindingsRequest) -> list[Finding]:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        return await self._findings.list_for_firewall(
            firewall_id=request.firewall_id,
            status=request.status,
            severity=request.severity,
            check_type=request.check_type,
        )
