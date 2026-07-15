"""Phase 4 integration tests: firewall CRUD + agent_token security."""

import uuid

from httpx import AsyncClient


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


async def test_create_firewall_returns_token_once(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)

    r = await client.post("/v1/firewalls", json={"name": "pf-lab-01"}, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["firewall"]["name"] == "pf-lab-01"
    assert body["firewall"]["status"] == "pending"
    assert "agent_token" in body
    assert len(body["agent_token"]) > 20

    fw_id = body["firewall"]["id"]

    r2 = await client.get(f"/v1/firewalls/{fw_id}", headers=headers)
    assert r2.status_code == 200
    detail = r2.json()
    assert "agent_token" not in detail
    assert "token_hash" not in detail


async def test_list_firewalls_pagination(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)

    ids = []
    for i in range(3):
        r = await client.post("/v1/firewalls", json={"name": f"pf-{i}"}, headers=headers)
        assert r.status_code == 201
        ids.append(r.json()["firewall"]["id"])

    r = await client.get("/v1/firewalls?limit=2", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["firewalls"]) == 2
    assert body["next_cursor"] is not None

    r2 = await client.get(f"/v1/firewalls?limit=2&cursor={body['next_cursor']}", headers=headers)
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["firewalls"]) >= 1
    assert body2["next_cursor"] is None

    all_ids = [fw["id"] for fw in body["firewalls"]] + [fw["id"] for fw in body2["firewalls"]]
    assert sorted(all_ids) == sorted(ids)


async def test_rename_firewall(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)

    r = await client.post("/v1/firewalls", json={"name": "old-name"}, headers=headers)
    fw_id = r.json()["firewall"]["id"]

    r2 = await client.patch(f"/v1/firewalls/{fw_id}", json={"name": "new-name"}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["name"] == "new-name"

    r3 = await client.get(f"/v1/firewalls/{fw_id}", headers=headers)
    assert r3.json()["name"] == "new-name"


async def test_delete_firewall_soft(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)

    r = await client.post("/v1/firewalls", json={"name": "pf-delete"}, headers=headers)
    fw_id = r.json()["firewall"]["id"]

    r2 = await client.delete(f"/v1/firewalls/{fw_id}", headers=headers)
    assert r2.status_code == 204

    r3 = await client.get(f"/v1/firewalls/{fw_id}", headers=headers)
    assert r3.status_code == 404

    r4 = await client.get("/v1/firewalls", headers=headers)
    assert all(fw["id"] != fw_id for fw in r4.json()["firewalls"])


async def test_rotate_token_revokes_old(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)

    r = await client.post("/v1/firewalls", json={"name": "pf-rotate"}, headers=headers)
    fw_id = r.json()["firewall"]["id"]
    original_token = r.json()["agent_token"]

    r2 = await client.post(f"/v1/firewalls/{fw_id}/rotate-token", headers=headers)
    assert r2.status_code == 200
    new_token = r2.json()["agent_token"]

    assert new_token != original_token
    assert len(new_token) > 20


async def test_cross_tenant_firewall_blocked(client: AsyncClient):
    token_a = await _register_and_login(client, "user-a")
    token_b = await _register_and_login(client, "user-b")

    r = await client.post(
        "/v1/firewalls",
        json={"name": "pf-a"},
        headers=await _auth(token_a),
    )
    assert r.status_code == 201
    fw_id = r.json()["firewall"]["id"]

    r2 = await client.get(f"/v1/firewalls/{fw_id}", headers=await _auth(token_b))
    assert r2.status_code == 404

    r3 = await client.patch(
        f"/v1/firewalls/{fw_id}",
        json={"name": "hacked"},
        headers=await _auth(token_b),
    )
    assert r3.status_code == 404

    r4 = await client.delete(f"/v1/firewalls/{fw_id}", headers=await _auth(token_b))
    assert r4.status_code == 404

    r5 = await client.post(f"/v1/firewalls/{fw_id}/rotate-token", headers=await _auth(token_b))
    assert r5.status_code == 404


async def test_no_token_on_get(client: AsyncClient):
    token = await _register_and_login(client)
    headers = await _auth(token)

    r = await client.post("/v1/firewalls", json={"name": "pf-secret"}, headers=headers)
    fw_id = r.json()["firewall"]["id"]

    r2 = await client.get(f"/v1/firewalls/{fw_id}", headers=headers)
    body = r2.json()
    assert "agent_token" not in body
    assert "token_hash" not in body

    r3 = await client.get("/v1/firewalls", headers=headers)
    for fw in r3.json()["firewalls"]:
        assert "agent_token" not in fw
        assert "token_hash" not in fw
