"""Fase 8: Stripe webhook handler.

This use case is the ONLY thing that mutates `subscriptions.tier` after
`RegisterIndividualAccount`/`RegisterMultiempresaAccount` created the initial
`free` row. Idempotency is enforced by the `webhook_events.event_id UNIQUE`
constraint (`WebhookEventRepository.exists` short-circuits before any mutation).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.protocols import (
    PaymentGateway,
    SubscriptionRepository,
    UnitOfWork,
    WebhookEventRepository,
)


@dataclass(frozen=True)
class ProcessStripeWebhookRequest:
    body: bytes
    signature: str


class ProcessStripeWebhook:
    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        webhook_events: WebhookEventRepository,
        gateway: PaymentGateway,
        uow: UnitOfWork,
    ) -> None:
        self._subscriptions = subscriptions
        self._webhook_events = webhook_events
        self._gateway = gateway
        self._uow = uow

    async def execute(self, request: ProcessStripeWebhookRequest) -> None:
        # Signature verification raises InvalidWebhookSignatureError on mismatch;
        # the router turns that into a 400 response.
        event = self._gateway.verify_webhook_signature(request.body, request.signature)

        # Idempotency: Stripe retries the same event.id on network failures. If we've
        # already processed it, no-op — do NOT mutate subscriptions again.
        if await self._webhook_events.exists(event.event_id):
            return

        obj = event.data.get("object", {}) if isinstance(event.data, dict) else {}

        if event.event_type == "checkout.session.completed":
            account_id_str = (obj.get("metadata") or {}).get("account_id")
            if account_id_str:
                account_id = uuid.UUID(account_id_str)
                await self._subscriptions.update_from_stripe_event(
                    account_id,
                    tier="pro",
                    status="active",
                    stripe_customer_id=obj.get("customer"),
                    stripe_subscription_id=obj.get("subscription"),
                )
        elif event.event_type in ("customer.subscription.updated",):
            account_id_str = (obj.get("metadata") or {}).get("account_id")
            if account_id_str:
                account_id = uuid.UUID(account_id_str)
                stripe_status = obj.get("status", "active")
                current_period_end_ts = obj.get("current_period_end")
                current_period_end = (
                    datetime.fromtimestamp(current_period_end_ts, tz=UTC)
                    if current_period_end_ts
                    else None
                )
                # Map Stripe status to our internal status + tier.
                if stripe_status in ("active", "trialing"):
                    internal_status = "active"
                    tier = "pro"
                elif stripe_status == "past_due":
                    internal_status = "past_due"
                    tier = "pro"  # grace period — keep access
                else:  # canceled, unpaid, incomplete_expired, etc.
                    internal_status = "canceled"
                    tier = "free"
                await self._subscriptions.update_from_stripe_event(
                    account_id,
                    tier=tier,
                    status=internal_status,
                    stripe_subscription_id=obj.get("id"),
                    current_period_end=current_period_end,
                )
        elif event.event_type == "customer.subscription.deleted":
            account_id_str = (obj.get("metadata") or {}).get("account_id")
            if account_id_str:
                account_id = uuid.UUID(account_id_str)
                await self._subscriptions.update_from_stripe_event(
                    account_id,
                    tier="free",
                    status="canceled",
                )
        # Any other event type is silently acknowledged (still recorded for dedup).

        await self._webhook_events.create(event.event_id, event.event_type)
        await self._uow.commit()
