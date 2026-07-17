"""Pure unit tests for KnownCveCheck — no database, uses a fake mapping (not the real
curated JSON)."""

import uuid

from app.application.checks.known_cve import KnownCveCheck
from app.domain.entities import Firewall, Snapshot

_FAKE_KNOWN_CVES = {
    "2.4.4-RELEASE": [
        {"cve_id": "CVE-2018-4019", "severity": "high", "description": "test description"}
    ]
}


def _firewall(pfsense_version: str | None = None) -> Firewall:
    return Firewall(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        name="pf-test",
        pfsense_version=pfsense_version,
    )


def _snapshot(firewall_id: uuid.UUID, pfsense_version: str | None) -> Snapshot:
    payload: dict = {}
    if pfsense_version is not None:
        payload["pfsense_version"] = pfsense_version
    return Snapshot(firewall_id=firewall_id, raw_payload=payload)


def test_version_with_mapped_cve_generates_finding() -> None:
    check = KnownCveCheck(known_cves=_FAKE_KNOWN_CVES)
    firewall = _firewall()
    snapshot = _snapshot(firewall.id, pfsense_version="2.4.4-RELEASE")

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1
    assert findings[0].check_type == "known_cve"
    assert findings[0].severity == "high"
    assert findings[0].details["cve_id"] == "CVE-2018-4019"


def test_version_without_mapped_cve_generates_no_finding() -> None:
    check = KnownCveCheck(known_cves=_FAKE_KNOWN_CVES)
    firewall = _firewall()
    snapshot = _snapshot(firewall.id, pfsense_version="2.7.2")

    findings = check.run(firewall, snapshot)

    assert findings == []


def test_falls_back_to_firewall_pfsense_version_when_snapshot_lacks_it() -> None:
    check = KnownCveCheck(known_cves=_FAKE_KNOWN_CVES)
    firewall = _firewall(pfsense_version="2.4.4-RELEASE")
    snapshot = _snapshot(firewall.id, pfsense_version=None)

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1


def test_no_version_available_generates_no_finding() -> None:
    check = KnownCveCheck(known_cves=_FAKE_KNOWN_CVES)
    firewall = _firewall()
    snapshot = _snapshot(firewall.id, pfsense_version=None)

    findings = check.run(firewall, snapshot)

    assert findings == []
