"""Strategy: detects two or more rules on the same interface with the same
effective (source, destination, port, protocol, action) tuple — one of them
is redundant. No security impact by itself, but indicates poor config hygiene
(docs/specs/fase2-prd.md sec 6.3).

No FastAPI/SQLAlchemy imports here on purpose — this is pure domain logic,
runnable and testable without a database (Clean Architecture boundary).
"""

from collections import defaultdict

from app.domain.entities import Finding, Firewall, Snapshot


class DuplicateRuleCheck:
    check_type = "duplicate_rule"

    def run(self, firewall: Firewall, snapshot: Snapshot) -> list[Finding]:
        rules = snapshot.raw_payload.get("rules") or []

        groups: dict[tuple, list[dict]] = defaultdict(list)
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            key = (
                rule.get("interface"),
                rule.get("source"),
                rule.get("destination"),
                rule.get("port"),
                rule.get("protocol"),
                rule.get("action"),
            )
            groups[key].append(rule)

        findings: list[Finding] = []
        for key, duplicated_rules in groups.items():
            if len(duplicated_rules) < 2:
                continue

            interface = key[0]
            findings.append(
                Finding(
                    firewall_id=firewall.id,
                    snapshot_id=snapshot.id,
                    check_type=self.check_type,
                    severity="low",
                    details={
                        "interface": interface,
                        "rules": duplicated_rules,
                    },
                )
            )

        return findings
