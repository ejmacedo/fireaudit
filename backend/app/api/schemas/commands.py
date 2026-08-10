import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateFirewallCommandPayload(BaseModel):
    command_type: str
    payload: dict


class ConfirmFirewallCommandPayload(BaseModel):
    password: str


class FirewallCommandResponse(BaseModel):
    id: uuid.UUID
    firewall_id: uuid.UUID
    user_id: uuid.UUID
    command_type: str
    payload: dict
    preview: dict | None
    status: str
    confirmed_at: datetime | None
    expires_at: datetime
    created_at: datetime | None
    applied_at: datetime | None


class ListFirewallCommandsResponse(BaseModel):
    commands: list[FirewallCommandResponse]


class AgentFirewallCommandResponse(BaseModel):
    id: uuid.UUID
    command_type: str
    payload: dict


class ListAgentFirewallCommandsResponse(BaseModel):
    commands: list[AgentFirewallCommandResponse]


class ReportFirewallCommandResultPayload(BaseModel):
    success: bool
    before_state: dict | None = None
    after_state: dict | None = None
    error: str | None = None
