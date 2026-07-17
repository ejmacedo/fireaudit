"""Pure unit tests for RiskyRuleCheck — no database, proves Clean Architecture decoupling."""

import uuid

from app.application.checks.risky_rule import RiskyRuleCheck
from app.domain.entities import Firewall, Snapshot


def _firewall() -> Firewall:
    return Firewall(id=uuid.uuid4(), organization_id=uuid.uuid4(), name="pf-test")


def _snapshot(firewall_id: uuid.UUID, rules: list[dict]) -> Snapshot:
    return Snapshot(firewall_id=firewall_id, raw_payload={"rules": rules})


def test_any_any_allow_rule_generates_one_finding() -> None:
    check = RiskyRuleCheck()
    firewall = _firewall()
    snapshot = _snapshot(
        firewall.id,
        rules=[
            {
                "interface": "wan",
                "action": "allow",
                "source": "any",
                "destination": "any",
                "protocol": "tcp",
                "port": None,
            }
        ],
    )

    findings = check.run(firewall, snapshot)

    assert len(findings) == 1
    assert findings[0].check_type == "risky_rule"
    assert findings[0].severity == "high"
    assert findings[0].details["interface"] == "wan"


def test_any_any_block_rule_generates_no_finding() -> None:
    check = RiskyRuleCheck()
    firewall = _firewall()
    snapshot = _snapshot(
        firewall.id,
        rules=[
            {
                "interface": "wan",
                "action": "block",
                "source": "any",
                "destination": "any",
            }
        ],
    )

    findings = check.run(firewall, snapshot)

    assert findings == []


def test_specific_rule_generates_no_finding() -> None:
    check = RiskyRuleCheck()
    firewall = _firewall()
    snapshot = _snapshot(
        firewall.id,
        rules=[
            {
                "interface": "wan",
                "action": "allow",
                "source": "203.0.113.0/24",
                "destination": "any",
                "protocol": "tcp",
                "port": 22,
            }
        ],
    )

    findings = check.run(firewall, snapshot)

    assert findings == []


def test_no_rules_generates_no_finding() -> None:
    check = RiskyRuleCheck()
    firewall = _firewall()
    snapshot = Snapshot(firewall_id=firewall.id, raw_payload={})

    findings = check.run(firewall, snapshot)

    assert findings == []
