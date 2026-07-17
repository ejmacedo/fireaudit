"""Strategy: detects a certificate that has expired or is about to expire.

No FastAPI/SQLAlchemy imports here on purpose — this is pure domain logic,
runnable and testable without a database (Clean Architecture boundary).
"""

from datetime import UTC, datetime, timedelta

from app.domain.entities import Finding, Firewall, Snapshot


class ExpiringCertCheck:
    check_type = "expiring_cert"

    def __init__(self, threshold_days: int) -> None:
        self._threshold_days = threshold_days

    def run(self, firewall: Firewall, snapshot: Snapshot) -> list[Finding]:
        findings: list[Finding] = []
        certificates = snapshot.raw_payload.get("certificates") or []
        now = datetime.now(UTC)
        cutoff = now + timedelta(days=self._threshold_days)

        for cert in certificates:
            if not isinstance(cert, dict):
                continue

            expires_at_raw = cert.get("expires_at")
            if not expires_at_raw:
                continue

            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except (TypeError, ValueError):
                continue

            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            if expires_at > cutoff:
                continue

            severity = "critical" if expires_at <= now else "high"

            findings.append(
                Finding(
                    firewall_id=firewall.id,
                    snapshot_id=snapshot.id,
                    check_type=self.check_type,
                    severity=severity,
                    details={
                        "name": cert.get("name"),
                        "expires_at": expires_at_raw,
                        "threshold_days": self._threshold_days,
                    },
                )
            )

        return findings
