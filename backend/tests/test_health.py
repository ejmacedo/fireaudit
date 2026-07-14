"""Phase 0 smoke test: /v1/health returns 200 (now backed by real Postgres via shared fixtures)."""

from httpx import AsyncClient


async def test_health_returns_200(client: AsyncClient):
    response = await client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
