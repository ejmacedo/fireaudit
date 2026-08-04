"""Integration tests for the alert channel/rule CRUD endpoints (real DB via httpx client)."""

import uuid

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

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
    r = await client.post("/v1/auth/login", json={"email": email, "password": "supersecret123"})
    assert r.status_code == 200
    return r.json()["access_token"], account_id


async def _set_tier(db_session: AsyncSession, account_id: str, tier: str) -> None:
    await db_session.execute(
        update(models.Subscription)
        .where(models.Subscription.account_id == uuid.UUID(account_id))
        .values(tier=tier)
    )
    await db_session.commit()


async def test_free_tier_cannot_create_alert_channel(client: AsyncClient, db_session: AsyncSession):
    token, _account_id = await _register_and_login(client, "free-ch")
    r = await client.post(
        "/v1/alerts/channels",
        json={"type": "email", "config": {"email": "ops@example.com"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "UPGRADE_REQUIRED"


async def test_pro_tier_creates_and_lists_alert_channel(
    client: AsyncClient, db_session: AsyncSession
):
    token, account_id = await _register_and_login(client, "pro-ch")
    await _set_tier(db_session, account_id, "pro")

    r = await client.post(
        "/v1/alerts/channels",
        json={"type": "email", "config": {"email": "ops@example.com"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    channel = r.json()
    assert channel["type"] == "email"
    assert channel["active"] is True

    r = await client.get(
        "/v1/alerts/channels",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["alert_channels"]) == 1
    assert r.json()["alert_channels"][0]["id"] == channel["id"]


async def test_create_alert_channel_rejects_unsupported_type(
    client: AsyncClient, db_session: AsyncSession
):
    token, account_id = await _register_and_login(client, "pro-ch-bad")
    await _set_tier(db_session, account_id, "pro")

    r = await client.post(
        "/v1/alerts/channels",
        json={"type": "slack", "config": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_ALERT_CHANNEL_TYPE"


async def test_pro_tier_creates_and_lists_alert_rule(client: AsyncClient, db_session: AsyncSession):
    token, account_id = await _register_and_login(client, "pro-rule")
    await _set_tier(db_session, account_id, "pro")

    r = await client.post(
        "/v1/alerts/channels",
        json={"type": "email", "config": {"email": "ops@example.com"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    channel_id = r.json()["id"]

    r = await client.post(
        "/v1/alerts/rules",
        json={
            "metric": "open_findings_count",
            "operator": "gte",
            "threshold": 5,
            "alert_channel_id": channel_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    rule = r.json()
    assert rule["operator"] == "gte"
    assert rule["alert_channel_id"] == channel_id

    r = await client.get(
        "/v1/alerts/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["alert_rules"]) == 1


async def test_create_alert_rule_rejects_invalid_operator(
    client: AsyncClient, db_session: AsyncSession
):
    token, account_id = await _register_and_login(client, "pro-rule-bad-op")
    await _set_tier(db_session, account_id, "pro")

    r = await client.post(
        "/v1/alerts/channels",
        json={"type": "email", "config": {"email": "ops@example.com"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    channel_id = r.json()["id"]

    r = await client.post(
        "/v1/alerts/rules",
        json={
            "metric": "open_findings_count",
            "operator": "not-valid",
            "threshold": 5,
            "alert_channel_id": channel_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_ALERT_RULE_OPERATOR"


async def test_create_alert_rule_rejects_channel_from_other_org(
    client: AsyncClient, db_session: AsyncSession
):
    token_a, account_a = await _register_and_login(client, "org-a")
    await _set_tier(db_session, account_a, "pro")
    token_b, account_b = await _register_and_login(client, "org-b")
    await _set_tier(db_session, account_b, "pro")

    r = await client.post(
        "/v1/alerts/channels",
        json={"type": "email", "config": {"email": "a@example.com"}},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    channel_id = r.json()["id"]

    r = await client.post(
        "/v1/alerts/rules",
        json={
            "metric": "open_findings_count",
            "operator": "gt",
            "threshold": 1,
            "alert_channel_id": channel_id,
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_CHANNEL_NOT_FOUND"
