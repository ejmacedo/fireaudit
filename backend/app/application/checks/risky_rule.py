"""Strategy: detects an "any-any" allow rule (source=any AND destination=any, action allow/pass).

No FastAPI/SQLAlchemy imports here on purpose — this is pure domain logic,
runnable and testable without a database (Clean Architecture boundary).
"""

from app.domain.entities import Finding, Firewall, Snapshot

_ALLOW_ACTIONS = {"allow", "pass"}
_ANY = "any"


class RiskyRuleCheck:
    check_type = "risky_rule"

    def run(self, firewall: Firewall, snapshot: Snapshot) -> list[Finding]:
        findings: list[Finding] = []
        rules = snapshot.raw_payload.get("rules") or []

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            action = rule.get("action")
            source = rule.get("source")
            destination = rule.get("destination")
            if action not in _ALLOW_ACTIONS:
                continue
            if source != _ANY or destination != _ANY:
                continue

            findings.append(
                Finding(
                    firewall_id=firewall.id,
                    snapshot_id=snapshot.id,
                    check_type=self.check_type,
                    severity="high",
                    details={
                        "interface": rule.get("interface"),
                        "rule": rule,
                    },
                )
            )

        return findings
