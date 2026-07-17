"""Pure unit tests for AgentOfflineCheck — no database, proves Clean Architecture decoupling."""

import uuid
from datetime import UTC, datetime, timedelta

from app.application.checks.agent_offline import AgentOfflineCheck
from app.domain.entities import Firewall, Snapshot

THRESHOLD_MINUTES = 30


def _firewall(last_seen_at: datetime | None) -> Firewall:
    return Firewall(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        name="pf-test",
        last_seen_at=last_seen_at,
    )


def _snapshot(firewall_id: uuid.UUID) -> Snapshot:
    return Snapshot(firewall_id=firewall_id, raw_payload={})


def test_stale_firewall_generates_one_finding() -> None:
    check = AgentOfflineCheck(threshold_minutes=THRESHOLD_MINUTES)
    firewall = _firewall(last_seen_at=datetime.now(UTC) - timedelta(minutes=60))
    snapshot = _snapshot(firewall.id)

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1
    assert findings[0].check_type == "agent_offline"
    assert findings[0].severity == "high"
    assert findings[0].firewall_id == firewall.id


def test_recent_firewall_generates_no_finding() -> None:
    check = AgentOfflineCheck(threshold_minutes=THRESHOLD_MINUTES)
    firewall = _firewall(last_seen_at=datetime.now(UTC) - timedelta(minutes=5))
    snapshot = _snapshot(firewall.id)

    findings = check.run(firewall, snapshot)

    assert findings == []


def test_firewall_never_seen_generates_no_finding() -> None:
    check = AgentOfflineCheck(threshold_minutes=THRESHOLD_MINUTES)
    firewall = _firewall(last_seen_at=None)
    snapshot = _snapshot(firewall.id)

    findings = check.run(firewall, snapshot)

    assert findings == []
