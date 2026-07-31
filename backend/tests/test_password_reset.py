"""Forgot-password flow: /v1/auth/forgot-password, /v1/auth/reset-password."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.infrastructure import models
from app.infrastructure.security import build_token_service


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient, email: str, password: str = "supersecret123") -> None:
    r = await client.post(
        "/v1/auth/register",
        json={
            "account_type": "individual",
            "email": email,
            "password": password,
            "organization_name": "Acme",
        },
    )
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, email: str, password: str = "supersecret123"):
    return await client.post("/v1/auth/login", json={"email": email, "password": password})


def _fake_email_sender(monkeypatch) -> AsyncMock:
    fake = AsyncMock()
    monkeypatch.setattr(deps, "get_email_sender", lambda: fake)
    return fake


async def test_forgot_password_existing_email_sends_email(client: AsyncClient, monkeypatch):
    email = _unique_email("fp-exists")
    await _register(client, email)
    fake_sender = _fake_email_sender(monkeypatch)

    r = await client.post("/v1/auth/forgot-password", json={"email": email})
    assert r.status_code == 202

    fake_sender.send.assert_called_once()
    _, kwargs = fake_sender.send.call_args
    assert kwargs["to"] == email


async def test_forgot_password_unknown_email_same_response_no_email_sent(
    client: AsyncClient, monkeypatch
):
    fake_sender = _fake_email_sender(monkeypatch)

    r = await client.post("/v1/auth/forgot-password", json={"email": _unique_email("fp-unknown")})
    assert r.status_code == 202
    fake_sender.send.assert_not_called()


async def _request_reset_and_capture_token(client: AsyncClient, email: str, monkeypatch) -> str:
    fake_sender = _fake_email_sender(monkeypatch)
    r = await client.post("/v1/auth/forgot-password", json={"email": email})
    assert r.status_code == 202
    fake_sender.send.assert_called_once()
    _, kwargs = fake_sender.send.call_args
    body_text: str = kwargs["body_text"]
    # body contains "...?token=<plain_token>"
    return body_text.split("token=")[1].split()[0].strip()


async def test_reset_password_with_valid_token_changes_password(client: AsyncClient, monkeypatch):
    email = _unique_email("fp-valid")
    await _register(client, email, password="old-password-123")
    plain_token = await _request_reset_and_capture_token(client, email, monkeypatch)

    r = await client.post(
        "/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "new-password-456"},
    )
    assert r.status_code == 204

    old_login = await _login(client, email, password="old-password-123")
    assert old_login.status_code == 401

    new_login = await _login(client, email, password="new-password-456")
    assert new_login.status_code == 200


async def test_reset_password_expired_token_returns_400(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    email = _unique_email("fp-expired")
    await _register(client, email)
    plain_token = await _request_reset_and_capture_token(client, email, monkeypatch)

    tokens_service = build_token_service()
    token_hash = tokens_service.hash_refresh_token(plain_token)
    await db_session.execute(
        update(models.PasswordResetToken)
        .where(models.PasswordResetToken.token_hash == token_hash)
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db_session.commit()

    r = await client.post(
        "/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "new-password-456"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_RESET_TOKEN"


async def test_reset_password_reused_token_returns_400(client: AsyncClient, monkeypatch):
    email = _unique_email("fp-reuse")
    await _register(client, email)
    plain_token = await _request_reset_and_capture_token(client, email, monkeypatch)

    first = await client.post(
        "/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "new-password-456"},
    )
    assert first.status_code == 204

    second = await client.post(
        "/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "another-password-789"},
    )
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "INVALID_RESET_TOKEN"


async def test_reset_password_unknown_token_returns_400(client: AsyncClient):
    r = await client.post(
        "/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "new-password-456"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_RESET_TOKEN"


async def test_reset_password_revokes_active_refresh_tokens(client: AsyncClient, monkeypatch):
    email = _unique_email("fp-revoke")
    await _register(client, email)
    old_tokens = (await _login(client, email)).json()

    plain_token = await _request_reset_and_capture_token(client, email, monkeypatch)
    r = await client.post(
        "/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "new-password-456"},
    )
    assert r.status_code == 204

    refresh_attempt = await client.post(
        "/v1/auth/refresh", json={"refresh_token": old_tokens["refresh_token"]}
    )
    assert refresh_attempt.status_code == 401


async def test_forgot_password_rate_limited_after_three_attempts_still_202(
    client: AsyncClient, monkeypatch
):
    email = _unique_email("fp-ratelimit")
    await _register(client, email)
    fake_sender = _fake_email_sender(monkeypatch)

    for _ in range(3):
        r = await client.post("/v1/auth/forgot-password", json={"email": email})
        assert r.status_code == 202
    assert fake_sender.send.call_count == 3

    r = await client.post("/v1/auth/forgot-password", json={"email": email})
    assert r.status_code == 202
    # 4th attempt is rate-limited: use case never runs, no additional email sent.
    assert fake_sender.send.call_count == 3
