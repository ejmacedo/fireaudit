"""Pure unit tests for ExpiringCertCheck — no database, proves Clean Architecture decoupling."""

import uuid
from datetime import UTC, datetime, timedelta

from app.application.checks.expiring_cert import ExpiringCertCheck
from app.domain.entities import Firewall, Snapshot

THRESHOLD_DAYS = 30


def _firewall() -> Firewall:
    return Firewall(id=uuid.uuid4(), organization_id=uuid.uuid4(), name="pf-test")


def _snapshot(firewall_id: uuid.UUID, certificates: list[dict]) -> Snapshot:
    return Snapshot(firewall_id=firewall_id, raw_payload={"certificates": certificates})


def test_cert_expiring_within_threshold_generates_high_finding() -> None:
    check = ExpiringCertCheck(threshold_days=THRESHOLD_DAYS)
    firewall = _firewall()
    expires_at = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    snapshot = _snapshot(
        firewall.id, certificates=[{"name": "webgui-cert", "expires_at": expires_at}]
    )

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1
    assert findings[0].check_type == "expiring_cert"
    assert findings[0].severity == "high"
    assert findings[0].details["name"] == "webgui-cert"


def test_cert_already_expired_generates_critical_finding() -> None:
    check = ExpiringCertCheck(threshold_days=THRESHOLD_DAYS)
    firewall = _firewall()
    expires_at = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    snapshot = _snapshot(
        firewall.id, certificates=[{"name": "webgui-cert", "expires_at": expires_at}]
    )

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1
    assert findings[0].severity == "critical"


def test_cert_with_long_validity_generates_no_finding() -> None:
    check = ExpiringCertCheck(threshold_days=THRESHOLD_DAYS)
    firewall = _firewall()
    expires_at = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    snapshot = _snapshot(
        firewall.id, certificates=[{"name": "webgui-cert", "expires_at": expires_at}]
    )

    findings = check.run(firewall, snapshot)

    assert findings == []


def test_no_certificates_generates_no_finding() -> None:
    check = ExpiringCertCheck(threshold_days=THRESHOLD_DAYS)
    firewall = _firewall()
    snapshot = Snapshot(firewall_id=firewall.id, raw_payload={})

    findings = check.run(firewall, snapshot)

    assert findings == []
