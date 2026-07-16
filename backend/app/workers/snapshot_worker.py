"""Snapshot processing worker — polls snapshots WHERE processing_status='queued'."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.infrastructure.repositories import SqlAlchemySnapshotRepository

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 30
_BATCH_SIZE = 10


async def _process_batch(session: AsyncSession) -> int:
    repo = SqlAlchemySnapshotRepository(session)
    snapshots = await repo.list_queued(limit=_BATCH_SIZE)
    for snapshot in snapshots:
        await repo.update_status(snapshot.id, "processing")
        await session.commit()
        # Phase 6: run compliance analysis here
        await repo.update_status(snapshot.id, "done")
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
