"""Fase 7 integration tests: findings, rules and vpn-tunnels endpoints."""

import uuid

from httpx import AsyncClient
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


async def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_firewall(client: AsyncClient, headers: dict, name: str = "pf-01") -> str:
    r = await client.post("/v1/firewalls", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["firewall"]["id"]


async def _insert_snapshot(
    db_session: AsyncSession, firewall_id: str, raw_payload: dict | None = None
) -> str:
    snapshot = models.Snapshot(
        id=uuid.uuid4(),
        firewall_id=uuid.UUID(firewall_id),
        raw_payload=raw_payload or {},
        processing_status="done",
    )
    db_session.add(snapshot)
    await db_session.flush()
    await db_session.commit()
    return str(snapshot.id)


async def _insert_finding(
    db_session: AsyncSession,
    firewall_id: str,
    snapshot_id: str,
    check_type: str = "agent_offline",
    severity: str = "critical",
    status_: str = "open",
) -> str:
    finding = models.Finding(
        id=uuid.uuid4(),
        firewall_id=uuid.UUID(firewall_id),
        snapshot_id=uuid.UUID(snapshot_id),
        check_type=check_type,
        severity=severity,
        details={"message": "test finding"},
        status=status_,
    )
    db_session.add(finding)
    await db_session.flush()
    await db_session.commit()
    return str(finding.id)


async def test_list_findings_empty_when_no_findings(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)
    fw_id = await _create_firewall(client, headers)

    r = await client.get(f"/v1/firewalls/{fw_id}/findings", headers=headers)
    assert r.status_code == 200
    assert r.json()["findings"] == []


async def test_list_findings_returns_created_findings(
    client: AsyncClient, db_session: AsyncSession
):
    token = await _register_and_login(client)
    headers = await _auth(token)
    fw_id = await _create_firewall(client, headers)

    snapshot_id = await _insert_snapshot(db_session, fw_id)
    await _insert_finding(db_session, fw_id, snapshot_id, check_type="agent_offline")

    r = await client.get(f"/v1/firewalls/{fw_id}/findings", headers=headers)
    assert r.status_code == 200
    findings = r.json()["findings"]
    assert len(findings) == 1
    assert findings[0]["check_type"] == "agent_offline"
    assert findings[0]["severity"] == "critical"
    assert findings[0]["status"] == "open"
    assert findings[0]["resolved_at"] is None


async def test_resolve_finding_sets_status_and_resolved_at(
    client: AsyncClient, db_session: AsyncSession
):
    token = await _register_and_login(client)
    headers = await _auth(token)
    fw_id = await _create_firewall(client, headers)

    snapshot_id = await _insert_snapshot(db_session, fw_id)
    finding_id = await _insert_finding(db_session, fw_id, snapshot_id)

    r = await client.patch(
        f"/v1/firewalls/{fw_id}/findings/{finding_id}",
        json={"status": "resolved"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None


async def test_open_findings_by_severity_reflected_on_firewall_list(
    client: AsyncClient, db_session: AsyncSession
):
    token = await _register_and_login(client)
    headers = await _auth(token)
    fw_id = await _create_firewall(client, headers)

    snapshot_id = await _insert_snapshot(db_session, fw_id)
    await _insert_finding(db_session, fw_id, snapshot_id, severity="critical")
    await _insert_finding(
        db_session, fw_id, snapshot_id, check_type="cert_expiring", severity="high"
    )
    # A resolved finding must not count.
    await _insert_finding(
        db_session,
        fw_id,
        snapshot_id,
        check_type="risky_rule",
        severity="low",
        status_="resolved",
    )

    r = await client.get("/v1/firewalls", headers=headers)
    assert r.status_code == 200
    fw = next(fw for fw in r.json()["firewalls"] if fw["id"] == fw_id)
    assert fw["open_findings_by_severity"] == {
        "critical": 1,
        "high": 1,
        "medium": 0,
        "low": 0,
    }

    r2 = await client.get(f"/v1/firewalls/{fw_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["open_findings_by_severity"] == {
        "critical": 1,
        "high": 1,
        "medium": 0,
        "low": 0,
    }


async def test_rules_and_vpn_tunnels_empty_without_snapshot(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)
    fw_id = await _create_firewall(client, headers)

    r = await client.get(f"/v1/firewalls/{fw_id}/rules", headers=headers)
    assert r.status_code == 200
    assert r.json()["rules"] == []

    r2 = await client.get(f"/v1/firewalls/{fw_id}/vpn-tunnels", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["vpn_tunnels"] == []


async def test_rules_and_vpn_tunnels_use_latest_snapshot(
    client: AsyncClient, db_session: AsyncSession
):
    token = await _register_and_login(client)
    headers = await _auth(token)
    fw_id = await _create_firewall(client, headers)

    await _insert_snapshot(
        db_session,
        fw_id,
        raw_payload={"rules": [{"id": "old"}], "vpn_tunnels": [{"id": "old-vpn"}]},
    )
    await _insert_snapshot(
        db_session,
        fw_id,
        raw_payload={"rules": [{"id": "new"}], "vpn_tunnels": [{"id": "new-vpn"}]},
    )

    r = await client.get(f"/v1/firewalls/{fw_id}/rules", headers=headers)
    assert r.status_code == 200
    assert r.json()["rules"] == [{"id": "new"}]

    r2 = await client.get(f"/v1/firewalls/{fw_id}/vpn-tunnels", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["vpn_tunnels"] == [{"id": "new-vpn"}]


async def test_cross_tenant_findings_rules_vpn_blocked(
    client: AsyncClient, db_session: AsyncSession
):
    token_a = await _register_and_login(client, "user-a")
    token_b = await _register_and_login(client, "user-b")

    fw_id = await _create_firewall(client, await _auth(token_a), "pf-a")
    snapshot_id = await _insert_snapshot(db_session, fw_id, raw_payload={"rules": [{"id": "x"}]})
    finding_id = await _insert_finding(db_session, fw_id, snapshot_id)

    headers_b = await _auth(token_b)

    r = await client.get(f"/v1/firewalls/{fw_id}/findings", headers=headers_b)
    assert r.status_code == 404

    r2 = await client.patch(
        f"/v1/firewalls/{fw_id}/findings/{finding_id}",
        json={"status": "resolved"},
        headers=headers_b,
    )
    assert r2.status_code == 404

    r3 = await client.get(f"/v1/firewalls/{fw_id}/rules", headers=headers_b)
    assert r3.status_code == 404

    r4 = await client.get(f"/v1/firewalls/{fw_id}/vpn-tunnels", headers=headers_b)
    assert r4.status_code == 404


async def test_resolve_finding_not_belonging_to_firewall_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    token = await _register_and_login(client)
    headers = await _auth(token)
    fw_id_1 = await _create_firewall(client, headers, "pf-1")
    fw_id_2 = await _create_firewall(client, headers, "pf-2")

    snapshot_id = await _insert_snapshot(db_session, fw_id_1)
    finding_id = await _insert_finding(db_session, fw_id_1, snapshot_id)

    r = await client.patch(
        f"/v1/firewalls/{fw_id_2}/findings/{finding_id}",
        json={"status": "resolved"},
        headers=headers,
    )
    assert r.status_code == 404
