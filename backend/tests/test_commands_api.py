"""Integration tests for Gerenciamento Remoto (Pilar 4): the /firewalls/{id}/commands
user-facing endpoints and the /agent/commands agent-facing endpoints, against the real
FastAPI app + Postgres (via the client/db_session fixtures)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import models


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(client: AsyncClient, prefix: str) -> tuple[str, str]:
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


async def _create_firewall_with_token(client: AsyncClient, jwt: str) -> tuple[str, str]:
    r = await client.post(
        "/v1/firewalls",
        json={"name": "pf-commands-test"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 201, r.text
    return r.json()["firewall"]["id"], r.json()["agent_token"]


async def _pro_user_with_firewall(
    client: AsyncClient, db_session: AsyncSession, prefix: str
) -> tuple[str, str, str, str]:
    """Returns (jwt, account_id, firewall_id, plain_agent_token) for a pro-tier user."""
    jwt, account_id = await _register_and_login(client, prefix)
    await _set_tier(db_session, account_id, "pro")
    fw_id, agent_token = await _create_firewall_with_token(client, jwt)
    return jwt, account_id, fw_id, agent_token


@pytest.mark.asyncio
async def test_free_tier_cannot_create_firewall_command(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id = await _register_and_login(client, "free-cmd")
    fw_id, _token = await _create_firewall_with_token(client, jwt)

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "UPGRADE_REQUIRED"


@pytest.mark.asyncio
async def test_pro_tier_creates_and_lists_firewall_command(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, _token = await _pro_user_with_firewall(client, db_session, "pro-cmd")

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block", "source": "1.2.3.4"}},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 201, r.text
    command = r.json()
    assert command["status"] == "pending_confirmation"
    assert command["firewall_id"] == fw_id
    assert command["preview"] == {"action": "block", "source": "1.2.3.4"}

    r = await client.get(f"/v1/firewalls/{fw_id}/commands", headers=_auth_header(jwt))
    assert r.status_code == 200
    assert len(r.json()["commands"]) == 1
    assert r.json()["commands"][0]["id"] == command["id"]


@pytest.mark.asyncio
async def test_create_firewall_command_rejects_invalid_type(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, _token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-bad-type"
    )

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "reboot", "payload": {}},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_COMMAND_TYPE"


@pytest.mark.asyncio
async def test_create_firewall_command_rejects_firewall_from_other_org(
    client: AsyncClient, db_session: AsyncSession
):
    _jwt_a, _account_a, fw_a, _token_a = await _pro_user_with_firewall(
        client, db_session, "org-a-cmd"
    )
    jwt_b, _account_b = await _register_and_login(client, "org-b-cmd")
    await _set_tier(db_session, _account_b, "pro")

    r = await client.post(
        f"/v1/firewalls/{fw_a}/commands",
        json={"command_type": "create_rule", "payload": {}},
        headers=_auth_header(jwt_b),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "FIREWALL_NOT_FOUND"


@pytest.mark.asyncio
async def test_confirm_firewall_command_rejects_wrong_password(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, _token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-wrongpw"
    )
    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt),
    )
    command_id = r.json()["id"]

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/{command_id}/confirm",
        json={"password": "totally-wrong"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_confirm_firewall_command_succeeds_then_rejects_second_confirm(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, _token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-confirm"
    )
    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt),
    )
    command_id = r.json()["id"]

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/{command_id}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    assert r.json()["confirmed_at"] is not None

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/{command_id}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "FIREWALL_COMMAND_NOT_PENDING"


@pytest.mark.asyncio
async def test_confirm_unknown_command_returns_404(client: AsyncClient, db_session: AsyncSession):
    jwt, _account_id, fw_id, _token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-404"
    )

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/{uuid.uuid4()}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "FIREWALL_COMMAND_NOT_FOUND"


@pytest.mark.asyncio
async def test_agent_poll_then_confirm_then_agent_reports_success(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, agent_token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-agent-ok"
    )
    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt),
    )
    command_id = r.json()["id"]

    # Not yet confirmed -> agent poll returns nothing.
    r = await client.get("/v1/agent/commands", headers=_auth_header(agent_token))
    assert r.status_code == 200
    assert r.json()["commands"] == []

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/{command_id}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 200

    r = await client.get("/v1/agent/commands", headers=_auth_header(agent_token))
    assert r.status_code == 200
    commands = r.json()["commands"]
    assert len(commands) == 1
    assert commands[0]["id"] == command_id
    assert commands[0]["command_type"] == "create_rule"

    # The confirmed command is now sent_to_agent from the user's perspective too.
    r = await client.get(f"/v1/firewalls/{fw_id}/commands", headers=_auth_header(jwt))
    assert r.json()["commands"][0]["status"] == "sent_to_agent"

    r = await client.post(
        f"/v1/agent/commands/{command_id}/result",
        json={
            "success": True,
            "before_state": {"rules": []},
            "after_state": {"rules": [{"action": "block"}]},
        },
        headers=_auth_header(agent_token),
    )
    assert r.status_code == 204

    r = await client.get(f"/v1/firewalls/{fw_id}/commands", headers=_auth_header(jwt))
    updated = r.json()["commands"][0]
    assert updated["status"] == "applied"
    assert updated["applied_at"] is not None


@pytest.mark.asyncio
async def test_agent_reports_failure_marks_command_failed(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, agent_token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-agent-fail"
    )
    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt),
    )
    command_id = r.json()["id"]
    await client.post(
        f"/v1/firewalls/{fw_id}/commands/{command_id}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt),
    )
    await client.get("/v1/agent/commands", headers=_auth_header(agent_token))

    r = await client.post(
        f"/v1/agent/commands/{command_id}/result",
        json={"success": False, "error": "pfSense API timeout"},
        headers=_auth_header(agent_token),
    )
    assert r.status_code == 204

    r = await client.get(f"/v1/firewalls/{fw_id}/commands", headers=_auth_header(jwt))
    assert r.json()["commands"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_agent_report_result_on_non_dispatched_command_returns_409(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, agent_token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-agent-409"
    )
    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt),
    )
    command_id = r.json()["id"]
    # Still pending_confirmation — never confirmed/dispatched.

    r = await client.post(
        f"/v1/agent/commands/{command_id}/result",
        json={"success": True, "before_state": {}, "after_state": {}},
        headers=_auth_header(agent_token),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "FIREWALL_COMMAND_NOT_AWAITING_RESULT"


@pytest.mark.asyncio
async def test_agent_commands_are_scoped_to_own_firewall(
    client: AsyncClient, db_session: AsyncSession
):
    jwt_a, _account_a, fw_a, agent_token_a = await _pro_user_with_firewall(
        client, db_session, "scope-a"
    )
    jwt_b, _account_b, fw_b, agent_token_b = await _pro_user_with_firewall(
        client, db_session, "scope-b"
    )

    r = await client.post(
        f"/v1/firewalls/{fw_a}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt_a),
    )
    command_a = r.json()["id"]
    await client.post(
        f"/v1/firewalls/{fw_a}/commands/{command_a}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt_a),
    )

    r = await client.post(
        f"/v1/firewalls/{fw_b}/commands",
        json={"command_type": "create_rule", "payload": {"action": "allow"}},
        headers=_auth_header(jwt_b),
    )
    command_b = r.json()["id"]
    await client.post(
        f"/v1/firewalls/{fw_b}/commands/{command_b}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt_b),
    )

    r = await client.get("/v1/agent/commands", headers=_auth_header(agent_token_a))
    ids = [c["id"] for c in r.json()["commands"]]
    assert ids == [command_a]

    r = await client.get("/v1/agent/commands", headers=_auth_header(agent_token_b))
    ids = [c["id"] for c in r.json()["commands"]]
    assert ids == [command_b]


async def _apply_create_rule_command(
    client: AsyncClient,
    jwt: str,
    agent_token: str,
    fw_id: str,
    *,
    before_state: dict,
    after_state: dict,
) -> str:
    """Runs a full create->confirm->agent-poll->agent-report-success cycle for a
    create_rule command and returns the applied command's id."""
    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "create_rule", "payload": {"action": "block"}},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 201, r.text
    command_id = r.json()["id"]

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/{command_id}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 200, r.text

    r = await client.get("/v1/agent/commands", headers=_auth_header(agent_token))
    assert r.status_code == 200

    r = await client.post(
        f"/v1/agent/commands/{command_id}/result",
        json={"success": True, "before_state": before_state, "after_state": after_state},
        headers=_auth_header(agent_token),
    )
    assert r.status_code == 204, r.text
    return command_id


@pytest.mark.asyncio
async def test_rollback_full_cycle_marks_original_change_rolled_back(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, agent_token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-rollback-ok"
    )
    await _apply_create_rule_command(
        client,
        jwt,
        agent_token,
        fw_id,
        before_state={"rules": []},
        after_state={"rules": [{"action": "block"}]},
    )

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/rollback",
        headers=_auth_header(jwt),
    )
    assert r.status_code == 201, r.text
    rollback = r.json()
    assert rollback["command_type"] == "rollback"
    assert rollback["status"] == "pending_confirmation"
    assert rollback["payload"]["restore_state"] == {"rules": []}
    rollback_id = rollback["id"]

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/{rollback_id}/confirm",
        json={"password": "supersecret123"},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 200, r.text

    r = await client.get("/v1/agent/commands", headers=_auth_header(agent_token))
    assert r.status_code == 200
    commands = r.json()["commands"]
    assert len(commands) == 1
    assert commands[0]["id"] == rollback_id
    assert commands[0]["command_type"] == "rollback"

    r = await client.post(
        f"/v1/agent/commands/{rollback_id}/result",
        json={
            "success": True,
            "before_state": {"rules": [{"action": "block"}]},
            "after_state": {"rules": []},
        },
        headers=_auth_header(agent_token),
    )
    assert r.status_code == 204, r.text

    r = await client.get(f"/v1/firewalls/{fw_id}/commands", headers=_auth_header(jwt))
    by_id = {c["id"]: c for c in r.json()["commands"]}
    assert by_id[rollback_id]["status"] == "applied"


@pytest.mark.asyncio
async def test_rollback_without_prior_change_returns_409(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id, fw_id, _token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-rollback-none"
    )

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/rollback",
        headers=_auth_header(jwt),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NO_CHANGE_TO_ROLL_BACK"


@pytest.mark.asyncio
async def test_rollback_rejects_firewall_from_other_org(
    client: AsyncClient, db_session: AsyncSession
):
    _jwt_a, _account_a, fw_a, _token_a = await _pro_user_with_firewall(
        client, db_session, "org-a-rollback"
    )
    jwt_b, account_b = await _register_and_login(client, "org-b-rollback")
    await _set_tier(db_session, account_b, "pro")

    r = await client.post(
        f"/v1/firewalls/{fw_a}/commands/rollback",
        headers=_auth_header(jwt_b),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "FIREWALL_NOT_FOUND"


@pytest.mark.asyncio
async def test_free_tier_cannot_rollback_firewall_command(
    client: AsyncClient, db_session: AsyncSession
):
    jwt, _account_id = await _register_and_login(client, "free-rollback")
    fw_id, _token = await _create_firewall_with_token(client, jwt)

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands/rollback",
        headers=_auth_header(jwt),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "UPGRADE_REQUIRED"


@pytest.mark.asyncio
async def test_create_firewall_command_rejects_rollback_type_directly(
    client: AsyncClient, db_session: AsyncSession
):
    """The generic create endpoint must not allow spoofing a rollback command —
    only the dedicated RollbackFirewallCommand use case may mint one."""
    jwt, _account_id, fw_id, _token = await _pro_user_with_firewall(
        client, db_session, "pro-cmd-rollback-spoof"
    )

    r = await client.post(
        f"/v1/firewalls/{fw_id}/commands",
        json={"command_type": "rollback", "payload": {}},
        headers=_auth_header(jwt),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_COMMAND_TYPE"
