"""Pure unit tests for ConfigDriftCheck — no database, proves Clean Architecture decoupling."""

import uuid

from app.application.checks.config_drift import ConfigDriftCheck
from app.domain.entities import Firewall, Snapshot


def _firewall() -> Firewall:
    return Firewall(id=uuid.uuid4(), organization_id=uuid.uuid4(), name="pf-test")


def _snapshot(firewall_id: uuid.UUID, payload: dict | None = None) -> Snapshot:
    return Snapshot(firewall_id=firewall_id, raw_payload=payload or {})


def test_no_previous_snapshot_generates_no_finding() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    snapshot = _snapshot(firewall.id, {"rules": [{"action": "allow"}]})

    findings = check.run(firewall, snapshot, previous_snapshot=None)

    assert findings == []


def test_identical_payloads_generate_no_finding() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    payload = {"rules": [{"action": "allow", "port": 22}], "system": {"hostname": "fw1"}}
    current = _snapshot(firewall.id, payload)
    previous = _snapshot(firewall.id, payload)

    findings = check.run(firewall, current, previous_snapshot=previous)

    assert findings == []


def test_changed_rules_section_generates_finding() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    current = _snapshot(firewall.id, {"rules": [{"action": "allow", "port": 443}]})
    previous = _snapshot(firewall.id, {"rules": [{"action": "allow", "port": 22}]})

    findings = check.run(firewall, current, previous_snapshot=previous)

    assert len(findings) == 1
    assert findings[0].check_type == "config_drift"
    assert findings[0].severity == "medium"
    assert "rules" in findings[0].details["changed_sections"]


def test_multiple_changed_sections_reported_in_single_finding() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    current = _snapshot(
        firewall.id,
        {
            "rules": [{"action": "block"}],
            "system": {"hostname": "fw-new"},
            "interfaces": [{"name": "em0"}],
        },
    )
    previous = _snapshot(
        firewall.id,
        {
            "rules": [{"action": "allow"}],
            "system": {"hostname": "fw-old"},
            "interfaces": [],
        },
    )

    findings = check.run(firewall, current, previous_snapshot=previous)

    assert len(findings) == 1
    changed = findings[0].details["changed_sections"]
    assert set(changed) == {"rules", "system", "interfaces"}


def test_only_untracked_fields_changed_generates_no_finding() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    current = _snapshot(firewall.id, {"rules": [{"action": "allow"}], "uptime": 9999})
    previous = _snapshot(firewall.id, {"rules": [{"action": "allow"}], "uptime": 1})

    findings = check.run(firewall, current, previous_snapshot=previous)

    assert findings == []


def test_finding_references_previous_snapshot_id() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    current = _snapshot(firewall.id, {"rules": [{"action": "block"}]})
    previous = _snapshot(firewall.id, {"rules": []})

    findings = check.run(firewall, current, previous_snapshot=previous)

    assert findings[0].details["previous_snapshot_id"] == str(previous.id)


def test_section_added_from_empty_counts_as_drift() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    current = _snapshot(firewall.id, {"vpn": [{"tunnel": "ipsec0"}]})
    previous = _snapshot(firewall.id, {})

    findings = check.run(firewall, current, previous_snapshot=previous)

    assert len(findings) == 1
    assert "vpn" in findings[0].details["changed_sections"]


def test_section_removed_counts_as_drift() -> None:
    check = ConfigDriftCheck()
    firewall = _firewall()
    current = _snapshot(firewall.id, {})
    previous = _snapshot(firewall.id, {"certificates": [{"cn": "fw.local"}]})

    findings = check.run(firewall, current, previous_snapshot=previous)

    assert len(findings) == 1
    assert "certificates" in findings[0].details["changed_sections"]
