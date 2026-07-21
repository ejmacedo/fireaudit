import uuid
from dataclasses import dataclass, field
from datetime import datetime


def _new_id() -> uuid.UUID:
    return uuid.uuid4()


@dataclass
class Account:
    account_type: str
    id: uuid.UUID = field(default_factory=_new_id)
    tax_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass
class Organization:
    account_id: uuid.UUID
    name: str
    id: uuid.UUID = field(default_factory=_new_id)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass
class RefreshToken:
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    id: uuid.UUID = field(default_factory=_new_id)
    revoked_at: datetime | None = None
    created_at: datetime | None = None


@dataclass
class User:
    account_id: uuid.UUID
    email: str
    password_hash: str
    id: uuid.UUID = field(default_factory=_new_id)
    role: str = "owner"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass
class Firewall:
    organization_id: uuid.UUID
    name: str
    id: uuid.UUID = field(default_factory=_new_id)
    pfsense_version: str | None = None
    status: str = "pending"
    last_seen_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass
class AgentToken:
    firewall_id: uuid.UUID
    token_hash: str
    id: uuid.UUID = field(default_factory=_new_id)
    status: str = "active"
    created_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass
class Snapshot:
    firewall_id: uuid.UUID
    raw_payload: dict
    id: uuid.UUID = field(default_factory=_new_id)
    processing_status: str = "queued"
    received_at: datetime | None = None
    processed_at: datetime | None = None


@dataclass
class Finding:
    firewall_id: uuid.UUID
    snapshot_id: uuid.UUID
    check_type: str
    severity: str
    details: dict
    id: uuid.UUID = field(default_factory=_new_id)
    status: str = "open"
    created_at: datetime | None = None
    resolved_at: datetime | None = None


@dataclass
class Subscription:
    account_id: uuid.UUID
    id: uuid.UUID = field(default_factory=_new_id)
    tier: str = "free"  # "free" | "pro" | "premium" (premium reserved for Fase 11)
    status: str = "active"  # "active" | "past_due" | "canceled"
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: datetime | None = None


@dataclass
class WebhookEvent:
    event_id: str
    event_type: str
    id: uuid.UUID = field(default_factory=_new_id)
    processed_at: datetime | None = None
