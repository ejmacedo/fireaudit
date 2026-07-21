from datetime import datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    current_period_end: datetime | None = None


class CheckoutSessionResponse(BaseModel):
    url: str
