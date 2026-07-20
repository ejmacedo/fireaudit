import uuid
from dataclasses import dataclass

from app.application.protocols import FindingRepository, FirewallRepository, UnitOfWork
from app.domain.entities import Finding
from app.domain.errors import FindingNotFoundError, FirewallNotFoundError


@dataclass(frozen=True)
class ResolveFindingRequest:
    firewall_id: uuid.UUID
    finding_id: uuid.UUID
    organization_id: uuid.UUID


class ResolveFinding:
    def __init__(
        self,
        firewalls: FirewallRepository,
        findings: FindingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._firewalls = firewalls
        self._findings = findings
        self._uow = uow

    async def execute(self, request: ResolveFindingRequest) -> Finding:
        fw = await self._firewalls.get_by_id(request.firewall_id)
        if fw is None or fw.deleted_at is not None or fw.organization_id != request.organization_id:
            raise FirewallNotFoundError

        finding = await self._findings.get_by_id(request.finding_id)
        if finding is None or finding.firewall_id != request.firewall_id:
            raise FindingNotFoundError

        result = await self._findings.update_status(request.finding_id, "resolved")
        await self._uow.commit()
        return result
