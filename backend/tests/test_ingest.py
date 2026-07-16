"""Phase 5 integration tests: snapshot ingest + HMAC + agent token validation."""

import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import models


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register_and_login(client: AsyncClient, prefix: str = "user") -> str:
    email = _unique_email(prefix)
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
    r = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_firewall_with_token(client: AsyncClient, jwt: str) -> tuple[str, str]:
    """Returns (firewall_id, plain_agent_token)."""
    r = await client.post(
        "/v1/firewalls",
        json={"name": "pf-ingest-test"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 201
    return r.json()["firewall"]["id"], r.json()["agent_token"]


def _make_payload() -> dict:
    return {
        "collected_at": "2026-07-16T12:00:00Z",
        "pfsense_version": "2.7.0",
        "system": {"cpu_pct": 10.5, "mem_pct": 40.0, "disk_pct": 20.0, "uptime_seconds": 3600},
    }


def _sign(plain_token: str, body: bytes) -> str:
    key = hashlib.sha256(plain_token.encode()).hexdigest()
    return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_ingest_valid_hmac_returns_202_and_queued(
    client: AsyncClient, db_session: AsyncSession
):
    jwt = await _register_and_login(client)
    fw_id, plain_token = await _create_firewall_with_token(client, jwt)

    body = json.dumps(_make_payload()).encode()
    sig = _sign(plain_token, body)

    r = await client.post(
        "/v1/ingest/snapshot",
        content=body,
        headers={
            "Authorization": f"Bearer {plain_token}",
            "X-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 202
    data = r.json()
    assert "snapshot_id" in data
    assert data["status"] == "queued"

    result = await db_session.execute(
        select(models.Snapshot).where(models.Snapshot.id == uuid.UUID(data["snapshot_id"]))
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.processing_status == "queued"
    assert str(row.firewall_id) == fw_id

    firewall = await db_session.get(models.Firewall, uuid.UUID(fw_id))
    assert firewall is not None
    assert firewall.status == "active"
    assert firewall.last_seen_at is not None
    assert firewall.pfsense_version == "2.7.0"


@pytest.mark.asyncio
async def test_ingest_invalid_hmac_returns_422_no_db_record(
    client: AsyncClient, db_session: AsyncSession
):
    jwt = await _register_and_login(client)
    fw_id, plain_token = await _create_firewall_with_token(client, jwt)

    body = json.dumps(_make_payload()).encode()

    r = await client.post(
        "/v1/ingest/snapshot",
        content=body,
        headers={
            "Authorization": f"Bearer {plain_token}",
            "X-Signature": "deadbeef",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_SIGNATURE"

    result = await db_session.execute(
        select(models.Snapshot).where(models.Snapshot.firewall_id == uuid.UUID(fw_id))
    )
    rows = result.scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_ingest_missing_signature_returns_422(client: AsyncClient):
    jwt = await _register_and_login(client)
    _fw_id, plain_token = await _create_firewall_with_token(client, jwt)

    body = json.dumps(_make_payload()).encode()

    r = await client.post(
        "/v1/ingest/snapshot",
        content=body,
        headers={
            "Authorization": f"Bearer {plain_token}",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_ingest_revoked_token_returns_401(client: AsyncClient):
    jwt = await _register_and_login(client)
    fw_id, plain_token = await _create_firewall_with_token(client, jwt)

    # Rotate (revokes old token)
    r = await client.post(
        f"/v1/firewalls/{fw_id}/rotate-token",
        headers=_auth_header(jwt),
    )
    assert r.status_code == 200

    body = json.dumps(_make_payload()).encode()
    sig = _sign(plain_token, body)

    r = await client.post(
        "/v1/ingest/snapshot",
        content=body,
        headers={
            "Authorization": f"Bearer {plain_token}",
            "X-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AGENT_TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_ingest_unknown_token_returns_401(client: AsyncClient):
    body = json.dumps(_make_payload()).encode()
    fake_token = "totally-fake-token-abc123"
    sig = _sign(fake_token, body)

    r = await client.post(
        "/v1/ingest/snapshot",
        content=body,
        headers={
            "Authorization": f"Bearer {fake_token}",
            "X-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_AGENT_TOKEN"


@pytest.mark.asyncio
async def test_ingest_rate_limit_is_scoped_to_agent_token(client: AsyncClient):
    jwt = await _register_and_login(client)
    _fw_id, plain_token = await _create_firewall_with_token(client, jwt)
    body = json.dumps(_make_payload()).encode()
    headers = {
        "Authorization": f"Bearer {plain_token}",
        "X-Signature": _sign(plain_token, body),
        "Content-Type": "application/json",
    }

    first = await client.post("/v1/ingest/snapshot", content=body, headers=headers)
    second = await client.post("/v1/ingest/snapshot", content=body, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_ingest_rejects_unexpected_top_level_field(
    client: AsyncClient, db_session: AsyncSession
):
    jwt = await _register_and_login(client)
    fw_id, plain_token = await _create_firewall_with_token(client, jwt)
    payload = _make_payload() | {"unexpected": "not-allowed"}
    body = json.dumps(payload).encode()

    r = await client.post(
        "/v1/ingest/snapshot",
        content=body,
        headers={
            "Authorization": f"Bearer {plain_token}",
            "X-Signature": _sign(plain_token, body),
            "Content-Type": "application/json",
        },
    )

    assert r.status_code == 422
    result = await db_session.execute(
        select(models.Snapshot).where(models.Snapshot.firewall_id == uuid.UUID(fw_id))
    )
    assert result.scalars().all() == []
