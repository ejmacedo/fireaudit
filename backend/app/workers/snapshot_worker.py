"""Snapshot processing worker — polls snapshots WHERE processing_status='queued'."""

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.checks.agent_offline import AgentOfflineCheck
from app.application.checks.config_drift import ConfigDriftCheck
from app.application.checks.duplicate_rule import DuplicateRuleCheck
from app.application.checks.expiring_cert import ExpiringCertCheck
from app.application.checks.known_cve import KnownCveCheck
from app.application.checks.risky_rule import RiskyRuleCheck
from app.application.use_cases.analyze_snapshot import AnalyzeSnapshot, AnalyzeSnapshotRequest
from app.application.use_cases.deliver_alerts import DeliverAlerts, DeliverAlertsRequest
from app.core.config import settings
from app.infrastructure.email_client import LoggingEmailSender, SmtpEmailSender
from app.infrastructure.repositories import (
    SqlAlchemyAlertChannelRepository,
    SqlAlchemyAlertDeliveryRepository,
    SqlAlchemyFindingRepository,
    SqlAlchemyFirewallRepository,
    SqlAlchemySnapshotRepository,
    SqlAlchemyUnitOfWork,
)

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 30
_BATCH_SIZE = 10
_KNOWN_CVES_PATH = (
    Path(__file__).resolve().parent.parent / "application" / "checks" / "data" / "known_cves.json"
)


@lru_cache(maxsize=1)
def _load_known_cves() -> dict[str, list[dict]]:
    with _KNOWN_CVES_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return {key: value for key, value in data.items() if not key.startswith("_")}


def _build_email_sender() -> SmtpEmailSender | LoggingEmailSender:
    if settings.smtp_host:
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            from_email=settings.smtp_from_email,
        )
    return LoggingEmailSender()


def _build_analyze_snapshot(session: AsyncSession) -> AnalyzeSnapshot:
    checks = [
        AgentOfflineCheck(threshold_minutes=settings.agent_offline_threshold_minutes),
        RiskyRuleCheck(),
        ExpiringCertCheck(threshold_days=settings.expiring_cert_threshold_days),
        KnownCveCheck(known_cves=_load_known_cves()),
        DuplicateRuleCheck(),
        ConfigDriftCheck(),
    ]
    return AnalyzeSnapshot(
        checks=checks,
        findings=SqlAlchemyFindingRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def _build_deliver_alerts(session: AsyncSession) -> DeliverAlerts:
    return DeliverAlerts(
        alert_channels=SqlAlchemyAlertChannelRepository(session),
        alert_deliveries=SqlAlchemyAlertDeliveryRepository(session),
        email_sender=_build_email_sender(),
        uow=SqlAlchemyUnitOfWork(session),
    )


async def _process_batch(session: AsyncSession) -> int:
    snapshot_repo = SqlAlchemySnapshotRepository(session)
    firewall_repo = SqlAlchemyFirewallRepository(session)
    analyze_snapshot = _build_analyze_snapshot(session)
    deliver_alerts = _build_deliver_alerts(session)

    snapshots = await snapshot_repo.list_queued(limit=_BATCH_SIZE)
    for snapshot in snapshots:
        await snapshot_repo.update_status(snapshot.id, "processing")
        await session.commit()

        firewall = await firewall_repo.get_by_id(snapshot.firewall_id)
        if firewall is not None:
            previous_snapshot = await snapshot_repo.get_previous_for_firewall(
                snapshot.firewall_id, before_id=snapshot.id
            )
            result = await analyze_snapshot.execute(
                AnalyzeSnapshotRequest(
                    firewall=firewall,
                    snapshot=snapshot,
                    previous_snapshot=previous_snapshot,
                )
            )
            if result.findings:
                await deliver_alerts.execute(
                    DeliverAlertsRequest(firewall=firewall, findings=result.findings)
                )

        await snapshot_repo.update_status(snapshot.id, "done")
        await session.commit()
    return len(snapshots)


async def run() -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    logger.info("Snapshot worker started, polling every %ds", _POLL_INTERVAL_SECONDS)
    while True:
        try:
            async with session_factory() as session:
                processed = await _process_batch(session)
                if processed:
                    logger.info("Processed %d snapshot(s)", processed)
        except Exception:
            logger.exception("Worker cycle failed")
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
