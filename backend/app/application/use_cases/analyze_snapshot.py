from dataclasses import dataclass

from app.application.protocols import AnalysisCheck, FindingRepository, UnitOfWork
from app.domain.entities import Firewall, Snapshot


@dataclass(frozen=True)
class AnalyzeSnapshotRequest:
    firewall: Firewall
    snapshot: Snapshot


@dataclass(frozen=True)
class AnalyzeSnapshotResult:
    findings_created: int


class AnalyzeSnapshot:
    """Runs every registered AnalysisCheck strategy against a snapshot.

    Idempotency: a check that already has an open Finding of its check_type
    for this firewall is skipped — repeated runs never duplicate findings.
    """

    def __init__(
        self,
        checks: list[AnalysisCheck],
        findings: FindingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._checks = checks
        self._findings = findings
        self._uow = uow

    async def execute(self, request: AnalyzeSnapshotRequest) -> AnalyzeSnapshotResult:
        created = 0
        for check in self._checks:
            existing = await self._findings.get_open_by_check_type(
                request.firewall.id, check.check_type
            )
            if existing is not None:
                continue

            for finding in check.run(request.firewall, request.snapshot):
                await self._findings.create(finding)
                created += 1

        await self._uow.commit()
        return AnalyzeSnapshotResult(findings_created=created)
