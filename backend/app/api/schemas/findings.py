import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FindingResponse(BaseModel):
    id: uuid.UUID
    firewall_id: uuid.UUID
    check_type: str
    severity: str
    status: str
    details: dict
    created_at: datetime | None
    resolved_at: datetime | None


class ListFindingsResponse(BaseModel):
    findings: list[FindingResponse]


class ResolveFindingPayload(BaseModel):
    status: Literal["resolved"]
