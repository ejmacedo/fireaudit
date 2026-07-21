"""Fase 8 tests: /v1/subscription, /v1/subscription/checkout-session, /v1/webhooks/stripe."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.application.protocols import CheckoutSession, ParsedWebhookEvent
from app.domain.errors import InvalidWebhookSignatureError
from app.infrastructure import models


async def _register_and_login(client: AsyncClient, prefix: str) -> tuple[str, str]:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/v1/auth/register",
        json={
            "account_type": "individual",
            "email": email,
            "password": "supersecret123",
            "organization_name": "Acme",
        },
    )
    assert r.status_code == 201, r.text
    account_id = r.json()["account_id"]
    r = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    assert r.status_code == 200
    return r.json()["access_token"], account_id


class _FakeGateway:
    def __init__(self) -> None:
        self.last_metadata = None

    def create_checkout_session(
        self, *, account_id, customer_email, success_url, cancel_url
    ) -> CheckoutSession:
        self.last_metadata = {
            "account_id": str(account_id),
            "customer_email": customer_email,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        return CheckoutSession(
            url="https://checkout.stripe.com/test_session",
            session_id="cs_test_123",
        )

    def verify_webhook_signature(self, body: bytes, signature: str) -> ParsedWebhookEvent:
        raise NotImplementedError("Override per-test via monkeypatch")


async def test_get_subscription_returns_free_for_new_account(
    client: AsyncClient, db_session: AsyncSession
):
    token, _account_id = await _register_and_login(client, "sub")
    r = await client.get(
        "/v1/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free"
    assert body["status"] == "active"


async def test_create_checkout_session_returns_gateway_url(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    token, account_id = await _register_and_login(client, "checkout")
    fake_gateway = _FakeGateway()
    monkeypatch.setattr(deps, "get_payment_gateway", lambda: fake_gateway)

    r = await client.post(
        "/v1/subscription/checkout-session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["url"] == "https://checkout.stripe.com/test_session"
    assert fake_gateway.last_metadata["account_id"] == account_id


async def test_create_checkout_session_conflict_if_already_pro(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    token, account_id = await _register_and_login(client, "already")
    await db_session.execute(
        update(models.Subscription)
        .where(models.Subscription.account_id == uuid.UUID(account_id))
        .values(tier="pro")
    )
    await db_session.commit()

    fake_gateway = _FakeGateway()
    monkeypatch.setattr(deps, "get_payment_gateway", lambda: fake_gateway)

    r = await client.post(
        "/v1/subscription/checkout-session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_SUBSCRIBED"


async def test_webhook_missing_signature_returns_400(client: AsyncClient):
    r = await client.post("/v1/webhooks/stripe", content=b"{}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "MISSING_SIGNATURE"


async def test_webhook_invalid_signature_returns_400(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    def _raise(body, sig):
        raise InvalidWebhookSignatureError("bad sig")

    fake_gateway = MagicMock()
    fake_gateway.verify_webhook_signature = _raise
    monkeypatch.setattr(deps, "get_payment_gateway", lambda: fake_gateway)

    r = await client.post(
        "/v1/webhooks/stripe",
        content=b'{"id":"evt_x"}',
        headers={"Stripe-Signature": "bad"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_SIGNATURE"


async def test_webhook_checkout_completed_promotes_to_pro(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    _token, account_id = await _register_and_login(client, "promote")

    def _verify(body, sig):
        return ParsedWebhookEvent(
            event_id="evt_test_1",
            event_type="checkout.session.completed",
            data={
                "object": {
                    "id": "cs_test_1",
                    "customer": "cus_test_1",
                    "subscription": "sub_test_1",
                    "metadata": {"account_id": account_id},
                }
            },
        )

    fake_gateway = MagicMock()
    fake_gateway.verify_webhook_signature = _verify
    monkeypatch.setattr(deps, "get_payment_gateway", lambda: fake_gateway)

    r = await client.post(
        "/v1/webhooks/stripe",
        content=b'{"id":"evt_test_1"}',
        headers={"Stripe-Signature": "test_sig"},
    )
    assert r.status_code == 200, r.text

    # Re-fetch in a fresh transaction so we see the committed state.
    await db_session.commit()
    sub = (
        await db_session.execute(
            select(models.Subscription).where(
                models.Subscription.account_id == uuid.UUID(account_id)
            )
        )
    ).scalar_one()
    assert sub.tier == "pro"
    assert sub.status == "active"
    assert sub.stripe_customer_id == "cus_test_1"
    assert sub.stripe_subscription_id == "sub_test_1"


async def test_webhook_idempotent_on_duplicate_event_id(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    _token, account_id = await _register_and_login(client, "idem")

    def _verify(body, sig):
        return ParsedWebhookEvent(
            event_id="evt_idem_1",
            event_type="checkout.session.completed",
            data={
                "object": {
                    "id": "cs_x",
                    "customer": "cus_x",
                    "subscription": "sub_x",
                    "metadata": {"account_id": account_id},
                }
            },
        )

    fake_gateway = MagicMock()
    fake_gateway.verify_webhook_signature = _verify
    monkeypatch.setattr(deps, "get_payment_gateway", lambda: fake_gateway)

    r1 = await client.post(
        "/v1/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "s"},
    )
    assert r1.status_code == 200

    # Manually flip tier back to free to prove second call is no-op
    await db_session.commit()
    await db_session.execute(
        update(models.Subscription)
        .where(models.Subscription.account_id == uuid.UUID(account_id))
        .values(tier="free")
    )
    await db_session.commit()

    r2 = await client.post(
        "/v1/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "s"},
    )
    assert r2.status_code == 200

    await db_session.commit()
    sub = (
        await db_session.execute(
            select(models.Subscription).where(
                models.Subscription.account_id == uuid.UUID(account_id)
            )
        )
    ).scalar_one()
    # Second call was deduped by webhook_events row, so tier stays as we manually set (free)
    assert sub.tier == "free"


async def test_webhook_subscription_deleted_downgrades_to_free(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    _token, account_id = await _register_and_login(client, "cancel")
    # Start as pro
    await db_session.execute(
        update(models.Subscription)
        .where(models.Subscription.account_id == uuid.UUID(account_id))
        .values(tier="pro", stripe_subscription_id="sub_cancel")
    )
    await db_session.commit()

    def _verify(body, sig):
        return ParsedWebhookEvent(
            event_id="evt_cancel_1",
            event_type="customer.subscription.deleted",
            data={
                "object": {
                    "id": "sub_cancel",
                    "metadata": {"account_id": account_id},
                }
            },
        )

    fake_gateway = MagicMock()
    fake_gateway.verify_webhook_signature = _verify
    monkeypatch.setattr(deps, "get_payment_gateway", lambda: fake_gateway)

    r = await client.post(
        "/v1/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "s"},
    )
    assert r.status_code == 200

    await db_session.commit()
    sub = (
        await db_session.execute(
            select(models.Subscription).where(
                models.Subscription.account_id == uuid.UUID(account_id)
            )
        )
    ).scalar_one()
    assert sub.tier == "free"
    assert sub.status == "canceled"


# Suppress unused-import warning for AsyncMock (kept for future extension).
_ = AsyncMock
