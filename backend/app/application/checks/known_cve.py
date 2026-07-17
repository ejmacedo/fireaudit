"""Strategy: detects a pfSense version with known, curated CVEs.

No FastAPI/SQLAlchemy imports here on purpose — this is pure domain logic,
runnable and testable without a database (Clean Architecture boundary).

The version-to-CVE mapping is not read from disk by this class — it is
injected via the constructor, so unit tests can supply a fake mapping
without touching the curated JSON file. See
`app/application/checks/data/known_cves.json` for the real curated data and
`docs/specs/fase12-operacao-manutencao.md` sec 2 for the monthly update process.
"""

from app.domain.entities import Finding, Firewall, Snapshot


class KnownCveCheck:
    check_type = "known_cve"

    def __init__(self, known_cves: dict[str, list[dict]]) -> None:
        self._known_cves = known_cves

    def run(self, firewall: Firewall, snapshot: Snapshot) -> list[Finding]:
        version = snapshot.raw_payload.get("pfsense_version") or firewall.pfsense_version
        if not version:
            return []

        cves = self._known_cves.get(version)
        if not cves:
            return []

        return [
            Finding(
                firewall_id=firewall.id,
                snapshot_id=snapshot.id,
                check_type=self.check_type,
                severity=cve.get("severity", "medium"),
                details={
                    "pfsense_version": version,
                    "cve_id": cve.get("cve_id"),
                    "description": cve.get("description"),
                },
            )
            for cve in cves
        ]
