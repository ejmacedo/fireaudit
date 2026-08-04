import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateAlertChannelPayload(BaseModel):
    type: str
    config: dict


class AlertChannelResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    type: str
    config: dict
    active: bool


class ListAlertChannelsResponse(BaseModel):
    alert_channels: list[AlertChannelResponse]


class CreateAlertRulePayload(BaseModel):
    metric: str
    operator: str
    threshold: float
    alert_channel_id: uuid.UUID
    firewall_id: uuid.UUID | None = None
    duration_minutes: int = 0


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    firewall_id: uuid.UUID | None
    metric: str
    operator: str
    threshold: float
    duration_minutes: int
    alert_channel_id: uuid.UUID
    active: bool
    created_by_user_id: uuid.UUID | None
    created_at: datetime | None
    updated_at: datetime | None


class ListAlertRulesResponse(BaseModel):
    alert_rules: list[AlertRuleResponse]
