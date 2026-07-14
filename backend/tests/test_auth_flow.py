"""Phase 3 integration tests: /auth/login, /auth/refresh, /auth/logout, /me, cross-tenant."""

import uuid

from httpx import AsyncClient


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient, email: str, org: str = "Acme") -> None:
    r = await client.post(
        "/v1/auth/register",
        json={
            "account_type": "individual",
            "email": email,
            "password": "supersecret123",
            "organization_name": org,
        },
    )
    assert r.status_code == 201


async def _login(client: AsyncClient, email: str, password: str = "supersecret123"):
    return await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )


async def test_login_success_returns_tokens(client: AsyncClient):
    email = _unique_email("alice")
    await _register(client, email)

    response = await _login(client, email)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


async def test_login_wrong_password_returns_401(client: AsyncClient):
    email = _unique_email("wrongpw")
    await _register(client, email)

    response = await _login(client, email, password="not-the-password")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email_returns_401_same_shape(client: AsyncClient):
    response = await _login(client, _unique_email("nobody"))
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


async def test_me_requires_bearer_token(client: AsyncClient):
    response = await client.get("/v1/me")
    assert response.status_code == 401


async def test_me_with_valid_token_returns_current_user(client: AsyncClient):
    email = _unique_email("bob")
    await _register(client, email, org="Bob Corp")
    tokens = (await _login(client, email)).json()

    response = await client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert body["account_type"] == "individual"
    assert len(body["organizations"]) == 1
    assert body["organizations"][0]["name"] == "Bob Corp"


async def test_me_with_invalid_token_returns_401(client: AsyncClient):
    response = await client.get(
        "/v1/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401


async def test_refresh_rotates_and_invalidates_previous(client: AsyncClient):
    email = _unique_email("charlie")
    await _register(client, email)
    first = (await _login(client, email)).json()

    refresh_1 = await client.post(
        "/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert refresh_1.status_code == 200
    new_tokens = refresh_1.json()
    assert new_tokens["refresh_token"] != first["refresh_token"]

    # Old refresh must now be invalid (rotation).
    reused = await client.post("/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_logout_revokes_refresh_token(client: AsyncClient):
    email = _unique_email("dan")
    await _register(client, email)
    tokens = (await _login(client, email)).json()

    logout = await client.post("/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 204

    reused = await client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


async def test_cross_tenant_me_returns_only_own_account(client: AsyncClient):
    """Phase 3 acceptance: two accounts with distinct orgs.
    Each user's /me sees strictly their own account and organizations."""
    email_a = _unique_email("user-a")
    email_b = _unique_email("user-b")
    await _register(client, email_a, org="Alpha Corp")
    await _register(client, email_b, org="Beta Corp")

    a = (await _login(client, email_a)).json()
    b = (await _login(client, email_b)).json()

    me_a = (
        await client.get("/v1/me", headers={"Authorization": f"Bearer {a['access_token']}"})
    ).json()
    me_b = (
        await client.get("/v1/me", headers={"Authorization": f"Bearer {b['access_token']}"})
    ).json()

    assert me_a["email"] == email_a
    assert me_a["account_id"] != me_b["account_id"]
    a_org_ids = {o["id"] for o in me_a["organizations"]}
    b_org_ids = {o["id"] for o in me_b["organizations"]}
    assert a_org_ids.isdisjoint(b_org_ids)


async def test_login_rate_limited_after_five_bad_attempts(client: AsyncClient):
    """After 5 bad attempts within 15 min for the same IP+email, 6th is rate-limited."""
    email = _unique_email("ratelimit")
    for _ in range(5):
        r = await _login(client, email, password="wrong-password")
        assert r.status_code == 401
    r = await _login(client, email, password="wrong-password")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
