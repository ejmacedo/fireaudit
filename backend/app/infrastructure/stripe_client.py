"""Stripe implementation of the PaymentGateway protocol.

Domain/application code depends only on `app.application.protocols.PaymentGateway`.
This module is the ONLY place in the backend allowed to import `stripe` directly.
"""

import uuid

import stripe

from app.application.protocols import CheckoutSession, ParsedWebhookEvent
from app.domain.errors import InvalidWebhookSignatureError


class StripePaymentGateway:
    def __init__(
        self,
        *,
        secret_key: str,
        webhook_secret: str,
        price_id_pro: str,
    ) -> None:
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        self._price_id_pro = price_id_pro
        stripe.api_key = secret_key

    def create_checkout_session(
        self,
        *,
        account_id: uuid.UUID,
        customer_email: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": self._price_id_pro, "quantity": 1}],
            customer_email=customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"account_id": str(account_id)},
            # Ensure webhook subscription events also carry account_id via subscription_data.
            subscription_data={"metadata": {"account_id": str(account_id)}},
        )
        return CheckoutSession(url=session.url, session_id=session.id)

    def verify_webhook_signature(self, body: bytes, signature: str) -> ParsedWebhookEvent:
        try:
            event = stripe.Webhook.construct_event(body, signature, self._webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise InvalidWebhookSignatureError(str(exc)) from exc
        # `event.data` is a stripe.StripeObject with the shape { "object": <resource>, ... }.
        # Convert the whole event to a plain dict using Stripe's `.to_dict()` and extract
        # `data` so the use case (which type-checks with isinstance(..., dict)) can read it.
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        return ParsedWebhookEvent(
            event_id=event_dict["id"],
            event_type=event_dict["type"],
            data=event_dict.get("data", {}),
        )
