import uuid
from dataclasses import dataclass

from app.application.protocols import SnapshotRepository, UnitOfWork
from app.domain.entities import Snapshot


@dataclass(frozen=True)
class IngestSnapshotRequest:
    firewall_id: uuid.UUID
    raw_payload: dict


@dataclass(frozen=True)
class IngestSnapshotResult:
    snapshot_id: uuid.UUID


class IngestSnapshot:
    def __init__(self, snapshots: SnapshotRepository, uow: UnitOfWork) -> None:
        self._snapshots = snapshots
        self._uow = uow

    async def execute(self, request: IngestSnapshotRequest) -> IngestSnapshotResult:
        snapshot = Snapshot(
            firewall_id=request.firewall_id,
            raw_payload=request.raw_payload,
        )
        snapshot = await self._snapshots.create(snapshot)
        await self._uow.commit()
        return IngestSnapshotResult(snapshot_id=snapshot.id)
