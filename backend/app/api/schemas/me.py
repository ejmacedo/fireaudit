import uuid

from pydantic import BaseModel


class OrganizationSummary(BaseModel):
    id: uuid.UUID
    name: str


class MeResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    account_id: uuid.UUID
    account_type: str
    organizations: list[OrganizationSummary]
