import uuid
from dataclasses import dataclass

from app.application.protocols import SubscriptionRepository
from app.domain.entities import Subscription
from app.domain.errors import SubscriptionNotFoundError


@dataclass(frozen=True)
class GetSubscriptionRequest:
    account_id: uuid.UUID


class GetSubscription:
    def __init__(self, subscriptions: SubscriptionRepository) -> None:
        self._subscriptions = subscriptions

    async def execute(self, request: GetSubscriptionRequest) -> Subscription:
        sub = await self._subscriptions.get_by_account_id(request.account_id)
        if sub is None:
            raise SubscriptionNotFoundError(str(request.account_id))
        return sub
