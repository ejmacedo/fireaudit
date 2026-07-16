import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    collected_at: datetime
    pfsense_version: str | None = None
    system: dict | None = None


class IngestSnapshotResponse(BaseModel):
    snapshot_id: uuid.UUID
    status: str
