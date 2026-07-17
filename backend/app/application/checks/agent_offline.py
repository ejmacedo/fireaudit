"""Strategy: detects a firewall whose agent has not checked in recently.

No FastAPI/SQLAlchemy imports here on purpose — this is pure domain logic,
runnable and testable without a database (Clean Architecture boundary).
"""

from datetime import UTC, datetime, timedelta

from app.domain.entities import Finding, Firewall, Snapshot


class AgentOfflineCheck:
    check_type = "agent_offline"

    def __init__(self, threshold_minutes: int) -> None:
        self._threshold_minutes = threshold_minutes

    def run(self, firewall: Firewall, snapshot: Snapshot) -> list[Finding]:
        if firewall.last_seen_at is None:
            return []

        cutoff = datetime.now(UTC) - timedelta(minutes=self._threshold_minutes)
        if firewall.last_seen_at >= cutoff:
            return []

        return [
            Finding(
                firewall_id=firewall.id,
                snapshot_id=snapshot.id,
                check_type=self.check_type,
                severity="high",
                details={
                    "last_seen_at": firewall.last_seen_at.isoformat(),
                    "threshold_minutes": self._threshold_minutes,
                },
            )
        ]
