"""Strategy: detects configuration drift by comparing the current snapshot
against the most recent processed snapshot for the same firewall.

Only the sections that carry security-relevant configuration are compared:
rules, interfaces, certificates, vpn, system. Volatile metadata outside
these keys is intentionally ignored to avoid noise.

No FastAPI/SQLAlchemy imports here on purpose — this is pure domain logic,
runnable and testable without a database (Clean Architecture boundary).
"""

from app.domain.entities import Finding, Firewall, Snapshot

_TRACKED_SECTIONS = ("rules", "interfaces", "certificates", "vpn", "system")


class ConfigDriftCheck:
    check_type = "config_drift"

    def run(
        self,
        firewall: Firewall,
        snapshot: Snapshot,
        *,
        previous_snapshot: Snapshot | None = None,
    ) -> list[Finding]:
        if previous_snapshot is None:
            return []

        changed_sections = [
            section
            for section in _TRACKED_SECTIONS
            if snapshot.raw_payload.get(section) != previous_snapshot.raw_payload.get(section)
        ]

        if not changed_sections:
            return []

        return [
            Finding(
                firewall_id=firewall.id,
                snapshot_id=snapshot.id,
                check_type=self.check_type,
                severity="medium",
                details={
                    "changed_sections": changed_sections,
                    "previous_snapshot_id": str(previous_snapshot.id),
                },
            )
        ]
