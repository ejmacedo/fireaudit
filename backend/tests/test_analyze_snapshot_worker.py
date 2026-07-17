"""Integration test: the snapshot worker generates exactly one Finding for a
stale firewall, and running it again never duplicates it."""

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


async def _register_and_login(client: AsyncClient) -> str:
    email = _unique_email("worker")
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
    r = await client.post("/v1/auth/login", json={"email": email, "password": "supersecret123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_worker_creates_one_finding_for_stale_firewall_and_does_not_duplicate(
    client: AsyncClient, db_session: AsyncSession
):
    jwt = await _register_and_login(client)
    r = await client.post(
        "/v1/firewalls",
        json={"name": "pf-stale"},
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

    processed_first = await _process_batch(db_session)
    assert processed_first == 1

    result = await db_session.execute(
        select(models.Finding).where(models.Finding.firewall_id == fw_id)
    )
    findings = result.scalars().all()
    assert len(findings) == 1
    assert findings[0].check_type == "agent_offline"

    # Second snapshot for the same still-stale firewall must not duplicate the finding.
    snapshot_row_2 = models.Snapshot(firewall_id=fw_id, raw_payload={}, processing_status="queued")
    db_session.add(snapshot_row_2)
    await db_session.commit()

    processed_second = await _process_batch(db_session)
    assert processed_second == 1

    result = await db_session.execute(
        select(models.Finding).where(models.Finding.firewall_id == fw_id)
    )
    findings_after = result.scalars().all()
    assert len(findings_after) == 1
