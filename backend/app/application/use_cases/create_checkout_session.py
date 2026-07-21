import uuid
from dataclasses import dataclass

from app.application.protocols import PaymentGateway, SubscriptionRepository
from app.domain.errors import AlreadySubscribedError, SubscriptionNotFoundError


@dataclass(frozen=True)
class CreateCheckoutSessionRequest:
    account_id: uuid.UUID
    customer_email: str
    success_url: str
    cancel_url: str


@dataclass(frozen=True)
class CreateCheckoutSessionResult:
    url: str
    session_id: str


class CreateCheckoutSession:
    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        gateway: PaymentGateway,
    ) -> None:
        self._subscriptions = subscriptions
        self._gateway = gateway

    async def execute(self, request: CreateCheckoutSessionRequest) -> CreateCheckoutSessionResult:
        sub = await self._subscriptions.get_by_account_id(request.account_id)
        if sub is None:
            raise SubscriptionNotFoundError(str(request.account_id))
        if sub.tier != "free":
            # Already on a paid tier — should not create a second checkout session
            # (would double-charge the customer or create orphaned Stripe subscriptions).
            raise AlreadySubscribedError(sub.tier)

        session = self._gateway.create_checkout_session(
            account_id=request.account_id,
            customer_email=request.customer_email,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return CreateCheckoutSessionResult(url=session.url, session_id=session.session_id)
