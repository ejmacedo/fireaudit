"""Pure unit tests for DuplicateRuleCheck — no database, proves Clean Architecture decoupling."""

import uuid

from app.application.checks.duplicate_rule import DuplicateRuleCheck
from app.domain.entities import Firewall, Snapshot


def _firewall() -> Firewall:
    return Firewall(id=uuid.uuid4(), organization_id=uuid.uuid4(), name="pf-test")


def _snapshot(firewall_id: uuid.UUID, rules: list[dict]) -> Snapshot:
    return Snapshot(firewall_id=firewall_id, raw_payload={"rules": rules})


def _rule(**overrides) -> dict:
    base = {
        "interface": "wan",
        "action": "allow",
        "source": "203.0.113.0/24",
        "destination": "any",
        "protocol": "tcp",
        "port": 22,
    }
    base.update(overrides)
    return base


def test_two_identical_rules_generate_one_finding() -> None:
    check = DuplicateRuleCheck()
    firewall = _firewall()
    snapshot = _snapshot(firewall.id, rules=[_rule(), _rule()])

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1
    assert findings[0].check_type == "duplicate_rule"
    assert findings[0].severity == "low"
    assert len(findings[0].details["rules"]) == 2


def test_rules_differing_only_in_irrelevant_field_still_count_as_duplicate() -> None:
    check = DuplicateRuleCheck()
    firewall = _firewall()
    snapshot = _snapshot(
        firewall.id,
        rules=[_rule(description="allow SSH from office"), _rule(description="legacy rule, keep")],
    )

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1


def test_different_rules_generate_no_finding() -> None:
    check = DuplicateRuleCheck()
    firewall = _firewall()
    snapshot = _snapshot(firewall.id, rules=[_rule(port=22), _rule(port=443)])

    findings = check.run(firewall, snapshot)

    assert findings == []


def test_no_rules_generates_no_finding() -> None:
    check = DuplicateRuleCheck()
    firewall = _firewall()
    snapshot = Snapshot(firewall_id=firewall.id, raw_payload={})

    findings = check.run(firewall, snapshot)

    assert findings == []
