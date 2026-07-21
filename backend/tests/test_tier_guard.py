"""Fase 8 tests: tier gating (403 UPGRADE_REQUIRED) on Pro-only routes."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import models


async def _register_and_login(client: AsyncClient, prefix: str) -> tuple[str, str]:
    """Register + login, return (access_token, account_id)."""
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


async def _create_firewall(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/v1/firewalls",
        json={"name": "pf-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["firewall"]["id"]


async def _set_tier(db_session: AsyncSession, account_id: str, tier: str) -> None:
    await db_session.execute(
        update(models.Subscription)
        .where(models.Subscription.account_id == uuid.UUID(account_id))
        .values(tier=tier)
    )
    await db_session.commit()


async def test_free_tier_findings_returns_upgrade_required(
    client: AsyncClient, db_session: AsyncSession
):
    token, _account_id = await _register_and_login(client, "free")
    fw_id = await _create_firewall(client, token)
    r = await client.get(
        f"/v1/firewalls/{fw_id}/findings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "UPGRADE_REQUIRED"


async def test_free_tier_rules_returns_upgrade_required(
    client: AsyncClient, db_session: AsyncSession
):
    token, _account_id = await _register_and_login(client, "free")
    fw_id = await _create_firewall(client, token)
    r = await client.get(
        f"/v1/firewalls/{fw_id}/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "UPGRADE_REQUIRED"


async def test_free_tier_vpn_tunnels_returns_upgrade_required(
    client: AsyncClient, db_session: AsyncSession
):
    token, _account_id = await _register_and_login(client, "free")
    fw_id = await _create_firewall(client, token)
    r = await client.get(
        f"/v1/firewalls/{fw_id}/vpn-tunnels",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "UPGRADE_REQUIRED"


async def test_pro_tier_findings_returns_200(client: AsyncClient, db_session: AsyncSession):
    token, account_id = await _register_and_login(client, "pro")
    fw_id = await _create_firewall(client, token)
    await _set_tier(db_session, account_id, "pro")
    r = await client.get(
        f"/v1/firewalls/{fw_id}/findings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


async def test_pro_tier_rules_returns_200(client: AsyncClient, db_session: AsyncSession):
    token, account_id = await _register_and_login(client, "pro")
    fw_id = await _create_firewall(client, token)
    await _set_tier(db_session, account_id, "pro")
    r = await client.get(
        f"/v1/firewalls/{fw_id}/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


async def test_free_tier_list_firewalls_still_works(client: AsyncClient, db_session: AsyncSession):
    """GET /v1/firewalls is NOT tier-gated — dashboard basic view is Free."""
    token, _account_id = await _register_and_login(client, "list")
    await _create_firewall(client, token)
    r = await client.get(
        "/v1/firewalls",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["firewalls"]) == 1


async def test_free_tier_get_firewall_still_works(client: AsyncClient, db_session: AsyncSession):
    """GET /v1/firewalls/{id} is NOT tier-gated — basic firewall detail is Free."""
    token, _account_id = await _register_and_login(client, "get")
    fw_id = await _create_firewall(client, token)
    r = await client.get(
        f"/v1/firewalls/{fw_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


async def test_free_tier_sees_severity_counts_for_teaser(
    client: AsyncClient, db_session: AsyncSession
):
    """Free tier CAN see open_findings_by_severity counts (used by the upgrade teaser)."""
    token, _account_id = await _register_and_login(client, "teaser")
    await _create_firewall(client, token)
    r = await client.get(
        "/v1/firewalls",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    fw = r.json()["firewalls"][0]
    assert "open_findings_by_severity" in fw
    assert set(fw["open_findings_by_severity"].keys()) == {"critical", "high", "medium", "low"}


async def test_subscription_backfill_works_for_existing_row(
    client: AsyncClient, db_session: AsyncSession
):
    """Register creates the subscription row; verify auth succeeds afterwards."""
    token, account_id = await _register_and_login(client, "sub")
    row = (
        await db_session.execute(
            select(models.Subscription).where(
                models.Subscription.account_id == uuid.UUID(account_id)
            )
        )
    ).scalar_one()
    assert row.tier == "free"
    assert row.status == "active"

    # Auth path (GET /v1/firewalls) requires the subscription row to be loadable —
    # this test confirms the AuthContext.subscription hydration works.
    r = await client.get(
        "/v1/firewalls",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
