import uuid
from dataclasses import dataclass

from app.application.protocols import PaymentGateway, SubscriptionRepository
from app.domain.errors import NoStripeCustomerError, SubscriptionNotFoundError


@dataclass(frozen=True)
class CreateBillingPortalSessionRequest:
    account_id: uuid.UUID
    return_url: str


@dataclass(frozen=True)
class CreateBillingPortalSessionResult:
    url: str


class CreateBillingPortalSession:
    """Lets a Pro customer self-manage their subscription (cancel, change card)
    via Stripe's hosted Customer Portal, instead of emailing support.

    Only usable once an account has a `stripe_customer_id` — i.e. it has
    completed at least one checkout. Free accounts that never upgraded have
    no Stripe customer yet, so there is nothing to manage.
    """

    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        gateway: PaymentGateway,
    ) -> None:
        self._subscriptions = subscriptions
        self._gateway = gateway

    async def execute(
        self, request: CreateBillingPortalSessionRequest
    ) -> CreateBillingPortalSessionResult:
        sub = await self._subscriptions.get_by_account_id(request.account_id)
        if sub is None:
            raise SubscriptionNotFoundError(str(request.account_id))
        if not sub.stripe_customer_id:
            raise NoStripeCustomerError(str(request.account_id))

        session = self._gateway.create_billing_portal_session(
            customer_id=sub.stripe_customer_id,
            return_url=request.return_url,
        )
        return CreateBillingPortalSessionResult(url=session.url)
