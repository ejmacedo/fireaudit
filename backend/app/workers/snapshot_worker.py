"""Snapshot processing worker — polls snapshots WHERE processing_status='queued'."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.checks.agent_offline import AgentOfflineCheck
from app.application.use_cases.analyze_snapshot import AnalyzeSnapshot, AnalyzeSnapshotRequest
from app.core.config import settings
from app.infrastructure.repositories import (
    SqlAlchemyFindingRepository,
    SqlAlchemyFirewallRepository,
    SqlAlchemySnapshotRepository,
    SqlAlchemyUnitOfWork,
)

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 30
_BATCH_SIZE = 10


def _build_analyze_snapshot(session: AsyncSession) -> AnalyzeSnapshot:
    checks = [AgentOfflineCheck(threshold_minutes=settings.agent_offline_threshold_minutes)]
    return AnalyzeSnapshot(
        checks=checks,
        findings=SqlAlchemyFindingRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


async def _process_batch(session: AsyncSession) -> int:
    snapshot_repo = SqlAlchemySnapshotRepository(session)
    firewall_repo = SqlAlchemyFirewallRepository(session)
    analyze_snapshot = _build_analyze_snapshot(session)

    snapshots = await snapshot_repo.list_queued(limit=_BATCH_SIZE)
    for snapshot in snapshots:
        await snapshot_repo.update_status(snapshot.id, "processing")
        await session.commit()

        firewall = await firewall_repo.get_by_id(snapshot.firewall_id)
        if firewall is not None:
            await analyze_snapshot.execute(
                AnalyzeSnapshotRequest(firewall=firewall, snapshot=snapshot)
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
