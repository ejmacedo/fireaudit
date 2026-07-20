import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateFirewallPayload(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class RenameFirewallPayload(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class FirewallResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    status: str
    pfsense_version: str | None
    last_seen_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    open_findings_by_severity: dict[str, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }


class CreateFirewallResponse(BaseModel):
    firewall: FirewallResponse
    agent_token: str


class RotateTokenResponse(BaseModel):
    agent_token: str


class ListFirewallsResponse(BaseModel):
    firewalls: list[FirewallResponse]
    next_cursor: uuid.UUID | None
