"""Unit test (fakes, no DB) proving AnalyzeSnapshot never duplicates an open Finding."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.checks.agent_offline import AgentOfflineCheck
from app.application.use_cases.analyze_snapshot import AnalyzeSnapshot, AnalyzeSnapshotRequest
from app.domain.entities import Finding, Firewall, Snapshot


class FakeFindingRepository:
    def __init__(self) -> None:
        self.created: list[Finding] = []

    async def create(self, finding: Finding) -> Finding:
        self.created.append(finding)
        return finding

    async def get_open_by_check_type(
        self, firewall_id: uuid.UUID, check_type: str
    ) -> Finding | None:
        for finding in self.created:
            if (
                finding.firewall_id == firewall_id
                and finding.check_type == check_type
                and finding.status == "open"
            ):
                return finding
        return None


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


@pytest.mark.asyncio
async def test_analyze_snapshot_does_not_duplicate_open_finding() -> None:
    findings = FakeFindingRepository()
    uow = FakeUnitOfWork()
    use_case = AnalyzeSnapshot(
        checks=[AgentOfflineCheck(threshold_minutes=30)],
        findings=findings,
        uow=uow,
    )
    firewall = Firewall(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        name="pf-test",
        last_seen_at=datetime.now(UTC) - timedelta(minutes=60),
    )
    snapshot = Snapshot(firewall_id=firewall.id, raw_payload={})

    first = await use_case.execute(AnalyzeSnapshotRequest(firewall=firewall, snapshot=snapshot))
    second = await use_case.execute(AnalyzeSnapshotRequest(firewall=firewall, snapshot=snapshot))

    assert first.findings_created == 1
    assert second.findings_created == 0
    assert len(findings.created) == 1
