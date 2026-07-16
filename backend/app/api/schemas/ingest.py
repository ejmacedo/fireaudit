import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SnapshotSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_pct: float | None = None
    mem_pct: float | None = None
    disk_pct: float | None = None
    uptime_seconds: int | None = None


class SnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collected_at: datetime
    pfsense_version: str | None = None
    system: SnapshotSystem | None = None
    interfaces: list[dict] | None = None
    rules: list[dict] | None = None
    vpn_tunnels: list[dict] | None = None
    certificates: list[dict] | None = None


class IngestSnapshotResponse(BaseModel):
    snapshot_id: uuid.UUID
    status: str
