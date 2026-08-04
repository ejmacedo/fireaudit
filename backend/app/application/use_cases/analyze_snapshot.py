from dataclasses import dataclass, field

from app.application.protocols import AnalysisCheck, FindingRepository, UnitOfWork
from app.domain.entities import Finding, Firewall, Snapshot


@dataclass(frozen=True)
class AnalyzeSnapshotRequest:
    firewall: Firewall
    snapshot: Snapshot
    previous_snapshot: Snapshot | None = field(default=None)


@dataclass(frozen=True)
class AnalyzeSnapshotResult:
    findings_created: int
    findings: list[Finding] = field(default_factory=list)


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
        created_findings: list[Finding] = []
        for check in self._checks:
            existing = await self._findings.get_open_by_check_type(
                request.firewall.id, check.check_type
            )
            if existing is not None:
                continue

            for finding in check.run(
                request.firewall, request.snapshot, previous_snapshot=request.previous_snapshot
            ):
                created_findings.append(await self._findings.create(finding))

        await self._uow.commit()
        return AnalyzeSnapshotResult(
            findings_created=len(created_findings), findings=created_findings
        )
