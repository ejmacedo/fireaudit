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
class User:
    account_id: uuid.UUID
    email: str
    password_hash: str
    id: uuid.UUID = field(default_factory=_new_id)
    role: str = "owner"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
