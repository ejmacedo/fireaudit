"""Integration test: snapshot worker delivers alerts to active channels for a new Finding."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import models
from app.workers.snapshot_worker import _process_batch


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register_and_login(client: AsyncClient) -> tuple[str, str]:
    email = _unique_email("deliver")
    r = await client.post(
        "/v1/auth/register",
        json={
            "account_type": "individual",
            "email": email,
            "password": "supersecret123",
            "organization_name": "Acme Corp",
        },
    )
    assert r.status_code == 201
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


@pytest.mark.asyncio
async def test_worker_delivers_alert_to_active_channel_when_finding_created(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, account_id = await _register_and_login(client)
    await _set_tier(db_session, account_id, "pro")

    r = await client.post(
        "/v1/firewalls",
        json={"name": "pf-stale"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201
    fw_id = uuid.UUID(r.json()["firewall"]["id"])

    r = await client.post(
        "/v1/alerts/channels",
        json={"type": "email", "config": {"email": "ops@example.com"}},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201
    channel_id = uuid.UUID(r.json()["id"])

    stale_last_seen = datetime.now(UTC) - timedelta(minutes=60)
    await db_session.execute(
        update(models.Firewall)
        .where(models.Firewall.id == fw_id)
        .values(last_seen_at=stale_last_seen, status="active")
    )
    snapshot_row = models.Snapshot(firewall_id=fw_id, raw_payload={}, processing_status="queued")
    db_session.add(snapshot_row)
    await db_session.commit()

    processed = await _process_batch(db_session)
    assert processed == 1

    finding_row = (
        await db_session.execute(select(models.Finding).where(models.Finding.firewall_id == fw_id))
    ).scalar_one()

    deliveries = (
        (
            await db_session.execute(
                select(models.AlertDelivery).where(
                    models.AlertDelivery.finding_id == finding_row.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(deliveries) == 1
    assert deliveries[0].alert_channel_id == channel_id
    assert deliveries[0].status == "sent"
    assert deliveries[0].sent_at is not None


@pytest.mark.asyncio
async def test_worker_skips_delivery_when_no_active_channels(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id = await _register_and_login(client)
    r = await client.post(
        "/v1/firewalls",
        json={"name": "pf-stale-no-channel"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201
    fw_id = uuid.UUID(r.json()["firewall"]["id"])

    stale_last_seen = datetime.now(UTC) - timedelta(minutes=60)
    await db_session.execute(
        update(models.Firewall)
        .where(models.Firewall.id == fw_id)
        .values(last_seen_at=stale_last_seen, status="active")
    )
    snapshot_row = models.Snapshot(firewall_id=fw_id, raw_payload={}, processing_status="queued")
    db_session.add(snapshot_row)
    await db_session.commit()

    processed = await _process_batch(db_session)
    assert processed == 1

    finding_row = (
        await db_session.execute(select(models.Finding).where(models.Finding.firewall_id == fw_id))
    ).scalar_one()

    deliveries = (
        (
            await db_session.execute(
                select(models.AlertDelivery).where(
                    models.AlertDelivery.finding_id == finding_row.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(deliveries) == 0
