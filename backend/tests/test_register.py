"""Phase 2 integration test: POST /v1/auth/register end-to-end against real Postgres."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import models


async def test_register_individual_creates_account_user_and_organization(
    client: AsyncClient, db_session: AsyncSession
):
    response = await client.post(
        "/v1/auth/register",
        json={
            "account_type": "individual",
            "email": "alice@example.com",
            "password": "supersecret123",
            "organization_name": "Acme",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["account_id"]
    assert body["user_id"]
    assert body["organization_id"]
    assert "password_hash" not in body
    assert "password" not in body

    user = (
        await db_session.execute(
            select(models.User).where(models.User.email == "alice@example.com")
        )
    ).scalar_one()
    assert user.password_hash != "supersecret123"
    assert user.password_hash.startswith("$argon2")


async def test_register_multiempresa_creates_account_and_user_only(
    client: AsyncClient, db_session: AsyncSession
):
    response = await client.post(
        "/v1/auth/register",
        json={
            "account_type": "multiempresa",
            "email": "priya@example.com",
            "password": "supersecret123",
            "tax_id": "12345678000199",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["account_id"]
    assert body["user_id"]
    assert body["organization_id"] is None

    account = (
        await db_session.execute(
            select(models.Account).where(models.Account.tax_id == "12345678000199")
        )
    ).scalar_one()
    assert account.account_type == "multiempresa"


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {
        "account_type": "individual",
        "email": "dup@example.com",
        "password": "supersecret123",
        "organization_name": "First",
    }
    first = await client.post("/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/v1/auth/register", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_register_invalid_payload_returns_422(client: AsyncClient):
    response = await client.post(
        "/v1/auth/register",
        json={"account_type": "individual", "email": "not-an-email"},
    )
    assert response.status_code == 422
