"""Unit tests (fakes, no DB) for the Gerenciamento Remoto use cases:
CreateFirewallCommand, ConfirmFirewallCommand, ListFirewallCommands,
PollFirewallCommands and ReportFirewallCommandResult."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.confirm_firewall_command import (
    ConfirmFirewallCommand,
    ConfirmFirewallCommandRequest,
)
from app.application.use_cases.create_firewall_command import (
    CreateFirewallCommand,
    CreateFirewallCommandRequest,
)
from app.application.use_cases.list_firewall_commands import (
    ListFirewallCommands,
    ListFirewallCommandsRequest,
)
from app.application.use_cases.poll_firewall_commands import (
    PollFirewallCommands,
    PollFirewallCommandsRequest,
)
from app.application.use_cases.report_firewall_command_result import (
    ReportFirewallCommandResult,
    ReportFirewallCommandResultRequest,
)
from app.application.use_cases.rollback_firewall_command import (
    RollbackFirewallCommand,
    RollbackFirewallCommandRequest,
)
from app.domain.entities import Firewall, FirewallCommand, User
from app.domain.errors import (
    ChangeAlreadyRolledBackError,
    FirewallCommandExpiredError,
    FirewallCommandNotAwaitingResultError,
    FirewallCommandNotFoundError,
    FirewallCommandNotPendingError,
    FirewallNotFoundError,
    InvalidCredentialsError,
    InvalidFirewallCommandTypeError,
    NoRemoteChangeToRollBackError,
)


class FakeFirewallRepository:
    def __init__(self) -> None:
        self.firewalls: dict[uuid.UUID, Firewall] = {}

    async def create(self, firewall: Firewall) -> Firewall:
        self.firewalls[firewall.id] = firewall
        return firewall

    async def get_by_id(self, firewall_id: uuid.UUID) -> Firewall | None:
        return self.firewalls.get(firewall_id)

    async def list_active_for_org(self, organization_id, cursor, limit):
        return [f for f in self.firewalls.values() if f.organization_id == organization_id]

    async def update(self, firewall: Firewall) -> Firewall:
        self.firewalls[firewall.id] = firewall
        return firewall

    async def record_check_in(self, firewall_id, pfsense_version) -> None:
        pass


class FakeFirewallCommandRepository:
    def __init__(self) -> None:
        self.commands: dict[uuid.UUID, FirewallCommand] = {}

    async def create(self, command: FirewallCommand) -> FirewallCommand:
        self.commands[command.id] = command
        return command

    async def get_by_id(self, command_id: uuid.UUID) -> FirewallCommand | None:
        return self.commands.get(command_id)

    async def update_status(
        self, command_id, *, status, confirmed_at=None, applied_at=None
    ) -> FirewallCommand:
        command = self.commands[command_id]
        command.status = status
        if confirmed_at is not None:
            command.confirmed_at = confirmed_at
        if applied_at is not None:
            command.applied_at = applied_at
        return command

    async def list_for_firewall(self, firewall_id: uuid.UUID) -> list[FirewallCommand]:
        return [c for c in self.commands.values() if c.firewall_id == firewall_id]

    async def list_sent_to_agent(self, firewall_id: uuid.UUID) -> list[FirewallCommand]:
        return [
            c
            for c in self.commands.values()
            if c.firewall_id == firewall_id and c.status == "sent_to_agent"
        ]


class FakeRemoteChangeLogRepository:
    def __init__(self) -> None:
        self.logs = []

    async def create(self, log):
        self.logs.append(log)
        return log

    async def get_latest_for_firewall(self, firewall_id: uuid.UUID):
        matching = [log for log in self.logs if log.firewall_id == firewall_id]
        return matching[-1] if matching else None

    async def list_for_firewall(self, firewall_id: uuid.UUID):
        return [log for log in self.logs if log.firewall_id == firewall_id]

    async def mark_rolled_back(self, log_id, *, rolled_back_by_user_id, rolled_back_at):
        log = next(log for log in self.logs if log.id == log_id)
        log.rolled_back_at = rolled_back_at
        log.rolled_back_by_user_id = rolled_back_by_user_id
        return log


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def create(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    async def update_password_hash(self, user_id, password_hash) -> None:
        self.users[user_id].password_hash = password_hash


class FakePasswordVerifier:
    def verify(self, plain: str, hashed: str) -> bool:
        return plain == hashed


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


def _make_firewall(org_id: uuid.UUID) -> Firewall:
    return Firewall(organization_id=org_id, name="pf-01")


def _make_user(account_id: uuid.UUID, password_hash: str = "correct-password") -> User:
    return User(account_id=account_id, email="owner@example.com", password_hash=password_hash)


@pytest.mark.asyncio
async def test_create_firewall_command_rejects_invalid_type() -> None:
    firewalls = FakeFirewallRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    use_case = CreateFirewallCommand(
        firewalls=firewalls,
        firewall_commands=FakeFirewallCommandRepository(),
        uow=FakeUnitOfWork(),
        ttl_minutes=15,
    )

    with pytest.raises(InvalidFirewallCommandTypeError):
        await use_case.execute(
            CreateFirewallCommandRequest(
                firewall_id=fw.id,
                organization_id=org_id,
                user_id=uuid.uuid4(),
                command_type="reboot",
                payload={},
            )
        )


@pytest.mark.asyncio
async def test_create_firewall_command_rejects_firewall_from_other_org() -> None:
    firewalls = FakeFirewallRepository()
    fw = await firewalls.create(_make_firewall(uuid.uuid4()))
    use_case = CreateFirewallCommand(
        firewalls=firewalls,
        firewall_commands=FakeFirewallCommandRepository(),
        uow=FakeUnitOfWork(),
        ttl_minutes=15,
    )

    with pytest.raises(FirewallNotFoundError):
        await use_case.execute(
            CreateFirewallCommandRequest(
                firewall_id=fw.id,
                organization_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                command_type="create_rule",
                payload={"action": "block"},
            )
        )


@pytest.mark.asyncio
async def test_create_firewall_command_persists_pending_with_expiry() -> None:
    firewalls = FakeFirewallRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    uow = FakeUnitOfWork()
    use_case = CreateFirewallCommand(
        firewalls=firewalls,
        firewall_commands=FakeFirewallCommandRepository(),
        uow=uow,
        ttl_minutes=15,
    )
    user_id = uuid.uuid4()

    before = datetime.now(UTC)
    command = await use_case.execute(
        CreateFirewallCommandRequest(
            firewall_id=fw.id,
            organization_id=org_id,
            user_id=user_id,
            command_type="create_rule",
            payload={"action": "block", "source": "1.2.3.4"},
        )
    )

    assert command.status == "pending_confirmation"
    assert command.firewall_id == fw.id
    assert command.user_id == user_id
    assert command.preview == {"action": "block", "source": "1.2.3.4"}
    assert before + timedelta(minutes=14) < command.expires_at < before + timedelta(minutes=16)
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_confirm_firewall_command_rejects_wrong_password() -> None:
    firewalls = FakeFirewallRepository()
    users = FakeUserRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    user = await users.create(_make_user(uuid.uuid4()))
    commands = FakeFirewallCommandRepository()
    command = await commands.create(
        FirewallCommand(
            firewall_id=fw.id,
            user_id=user.id,
            command_type="create_rule",
            payload={},
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    use_case = ConfirmFirewallCommand(
        firewalls=firewalls,
        firewall_commands=commands,
        users=users,
        verifier=FakePasswordVerifier(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            ConfirmFirewallCommandRequest(
                firewall_id=fw.id,
                command_id=command.id,
                organization_id=org_id,
                user_id=user.id,
                password="wrong-password",
            )
        )
    assert commands.commands[command.id].status == "pending_confirmation"


@pytest.mark.asyncio
async def test_confirm_firewall_command_rejects_already_confirmed() -> None:
    firewalls = FakeFirewallRepository()
    users = FakeUserRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    user = await users.create(_make_user(uuid.uuid4()))
    commands = FakeFirewallCommandRepository()
    command = await commands.create(
        FirewallCommand(
            firewall_id=fw.id,
            user_id=user.id,
            command_type="create_rule",
            payload={},
            status="confirmed",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    use_case = ConfirmFirewallCommand(
        firewalls=firewalls,
        firewall_commands=commands,
        users=users,
        verifier=FakePasswordVerifier(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(FirewallCommandNotPendingError):
        await use_case.execute(
            ConfirmFirewallCommandRequest(
                firewall_id=fw.id,
                command_id=command.id,
                organization_id=org_id,
                user_id=user.id,
                password="correct-password",
            )
        )


@pytest.mark.asyncio
async def test_confirm_firewall_command_rejects_expired_and_marks_it() -> None:
    firewalls = FakeFirewallRepository()
    users = FakeUserRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    user = await users.create(_make_user(uuid.uuid4()))
    commands = FakeFirewallCommandRepository()
    command = await commands.create(
        FirewallCommand(
            firewall_id=fw.id,
            user_id=user.id,
            command_type="create_rule",
            payload={},
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    uow = FakeUnitOfWork()
    use_case = ConfirmFirewallCommand(
        firewalls=firewalls,
        firewall_commands=commands,
        users=users,
        verifier=FakePasswordVerifier(),
        uow=uow,
    )

    with pytest.raises(FirewallCommandExpiredError):
        await use_case.execute(
            ConfirmFirewallCommandRequest(
                firewall_id=fw.id,
                command_id=command.id,
                organization_id=org_id,
                user_id=user.id,
                password="correct-password",
            )
        )
    assert commands.commands[command.id].status == "expired"
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_confirm_firewall_command_succeeds_and_commits() -> None:
    firewalls = FakeFirewallRepository()
    users = FakeUserRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    user = await users.create(_make_user(uuid.uuid4()))
    commands = FakeFirewallCommandRepository()
    command = await commands.create(
        FirewallCommand(
            firewall_id=fw.id,
            user_id=user.id,
            command_type="create_rule",
            payload={"action": "block"},
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    uow = FakeUnitOfWork()
    use_case = ConfirmFirewallCommand(
        firewalls=firewalls,
        firewall_commands=commands,
        users=users,
        verifier=FakePasswordVerifier(),
        uow=uow,
    )

    confirmed = await use_case.execute(
        ConfirmFirewallCommandRequest(
            firewall_id=fw.id,
            command_id=command.id,
            organization_id=org_id,
            user_id=user.id,
            password="correct-password",
        )
    )

    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_at is not None
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_confirm_firewall_command_rejects_command_from_other_firewall() -> None:
    firewalls = FakeFirewallRepository()
    users = FakeUserRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    other_fw = await firewalls.create(_make_firewall(org_id))
    user = await users.create(_make_user(uuid.uuid4()))
    commands = FakeFirewallCommandRepository()
    command = await commands.create(
        FirewallCommand(
            firewall_id=other_fw.id,
            user_id=user.id,
            command_type="create_rule",
            payload={},
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    use_case = ConfirmFirewallCommand(
        firewalls=firewalls,
        firewall_commands=commands,
        users=users,
        verifier=FakePasswordVerifier(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(FirewallCommandNotFoundError):
        await use_case.execute(
            ConfirmFirewallCommandRequest(
                firewall_id=fw.id,
                command_id=command.id,
                organization_id=org_id,
                user_id=user.id,
                password="correct-password",
            )
        )


@pytest.mark.asyncio
async def test_list_firewall_commands_rejects_firewall_from_other_org() -> None:
    firewalls = FakeFirewallRepository()
    fw = await firewalls.create(_make_firewall(uuid.uuid4()))
    use_case = ListFirewallCommands(
        firewalls=firewalls, firewall_commands=FakeFirewallCommandRepository()
    )

    with pytest.raises(FirewallNotFoundError):
        await use_case.execute(
            ListFirewallCommandsRequest(firewall_id=fw.id, organization_id=uuid.uuid4())
        )


@pytest.mark.asyncio
async def test_list_firewall_commands_returns_only_for_firewall() -> None:
    firewalls = FakeFirewallRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    other_fw = await firewalls.create(_make_firewall(org_id))
    commands = FakeFirewallCommandRepository()
    own = await commands.create(
        FirewallCommand(
            firewall_id=fw.id,
            user_id=uuid.uuid4(),
            command_type="create_rule",
            payload={},
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    await commands.create(
        FirewallCommand(
            firewall_id=other_fw.id,
            user_id=uuid.uuid4(),
            command_type="create_rule",
            payload={},
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    use_case = ListFirewallCommands(firewalls=firewalls, firewall_commands=commands)

    listed = await use_case.execute(
        ListFirewallCommandsRequest(firewall_id=fw.id, organization_id=org_id)
    )

    assert [c.id for c in listed] == [own.id]


@pytest.mark.asyncio
async def test_poll_firewall_commands_dispatches_only_confirmed() -> None:
    commands = FakeFirewallCommandRepository()
    firewall_id = uuid.uuid4()
    confirmed = await commands.create(
        FirewallCommand(
            firewall_id=firewall_id,
            user_id=uuid.uuid4(),
            command_type="create_rule",
            payload={},
            status="confirmed",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    pending = await commands.create(
        FirewallCommand(
            firewall_id=firewall_id,
            user_id=uuid.uuid4(),
            command_type="create_rule",
            payload={},
            status="pending_confirmation",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    use_case = PollFirewallCommands(firewall_commands=commands)

    dispatched = await use_case.execute(PollFirewallCommandsRequest(firewall_id=firewall_id))

    assert [c.id for c in dispatched] == [confirmed.id]
    assert commands.commands[confirmed.id].status == "sent_to_agent"
    assert commands.commands[pending.id].status == "pending_confirmation"


@pytest.mark.asyncio
async def test_report_firewall_command_result_rejects_when_not_sent_to_agent() -> None:
    commands = FakeFirewallCommandRepository()
    firewall_id = uuid.uuid4()
    command = await commands.create(
        FirewallCommand(
            firewall_id=firewall_id,
            user_id=uuid.uuid4(),
            command_type="create_rule",
            payload={},
            status="pending_confirmation",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    use_case = ReportFirewallCommandResult(
        firewall_commands=commands,
        remote_change_logs=FakeRemoteChangeLogRepository(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(FirewallCommandNotAwaitingResultError):
        await use_case.execute(
            ReportFirewallCommandResultRequest(
                firewall_id=firewall_id, command_id=command.id, success=True
            )
        )


@pytest.mark.asyncio
async def test_report_firewall_command_result_failure_marks_failed_without_log() -> None:
    commands = FakeFirewallCommandRepository()
    logs = FakeRemoteChangeLogRepository()
    firewall_id = uuid.uuid4()
    command = await commands.create(
        FirewallCommand(
            firewall_id=firewall_id,
            user_id=uuid.uuid4(),
            command_type="create_rule",
            payload={},
            status="sent_to_agent",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    uow = FakeUnitOfWork()
    use_case = ReportFirewallCommandResult(
        firewall_commands=commands, remote_change_logs=logs, uow=uow
    )

    await use_case.execute(
        ReportFirewallCommandResultRequest(
            firewall_id=firewall_id,
            command_id=command.id,
            success=False,
            error="pfSense API timeout",
        )
    )

    assert commands.commands[command.id].status == "failed"
    assert logs.logs == []
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_report_firewall_command_result_success_writes_hash_chained_log() -> None:
    commands = FakeFirewallCommandRepository()
    logs = FakeRemoteChangeLogRepository()
    firewall_id = uuid.uuid4()
    user_id = uuid.uuid4()
    first_command = await commands.create(
        FirewallCommand(
            firewall_id=firewall_id,
            user_id=user_id,
            command_type="create_rule",
            payload={},
            status="sent_to_agent",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    uow = FakeUnitOfWork()
    use_case = ReportFirewallCommandResult(
        firewall_commands=commands, remote_change_logs=logs, uow=uow
    )

    await use_case.execute(
        ReportFirewallCommandResultRequest(
            firewall_id=firewall_id,
            command_id=first_command.id,
            success=True,
            before_state={"rules": []},
            after_state={"rules": [{"action": "block"}]},
        )
    )

    assert commands.commands[first_command.id].status == "applied"
    assert commands.commands[first_command.id].applied_at is not None
    assert len(logs.logs) == 1
    first_log = logs.logs[0]
    assert first_log.firewall_command_id == first_command.id
    assert first_log.user_id == user_id
    assert first_log.record_hash

    # A second applied command on the same firewall must chain onto the first hash.
    second_command = await commands.create(
        FirewallCommand(
            firewall_id=firewall_id,
            user_id=user_id,
            command_type="create_rule",
            payload={},
            status="sent_to_agent",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    await use_case.execute(
        ReportFirewallCommandResultRequest(
            firewall_id=firewall_id,
            command_id=second_command.id,
            success=True,
            before_state={"rules": [{"action": "block"}]},
            after_state={"rules": [{"action": "block"}, {"action": "allow"}]},
        )
    )

    assert len(logs.logs) == 2
    second_log = logs.logs[1]
    assert second_log.record_hash != first_log.record_hash

    # Tampering with the first log's after_state changes the hash that would be
    # recomputed for it, which is exactly what would be detected by a chain replay.
    import hashlib
    import json

    recomputed_first = hashlib.sha256(
        json.dumps(
            {
                "previous_hash": "",
                "before_state": {"rules": []},
                "after_state": {"rules": [{"action": "block"}]},
                "applied_at": first_log.applied_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert recomputed_first == first_log.record_hash


@pytest.mark.asyncio
async def test_rollback_firewall_command_rejects_firewall_from_other_org() -> None:
    firewalls = FakeFirewallRepository()
    fw = await firewalls.create(_make_firewall(uuid.uuid4()))
    use_case = RollbackFirewallCommand(
        firewalls=firewalls,
        firewall_commands=FakeFirewallCommandRepository(),
        remote_change_logs=FakeRemoteChangeLogRepository(),
        uow=FakeUnitOfWork(),
        ttl_minutes=15,
    )

    with pytest.raises(FirewallNotFoundError):
        await use_case.execute(
            RollbackFirewallCommandRequest(
                firewall_id=fw.id,
                organization_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_rollback_firewall_command_rejects_when_no_change_exists() -> None:
    firewalls = FakeFirewallRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    use_case = RollbackFirewallCommand(
        firewalls=firewalls,
        firewall_commands=FakeFirewallCommandRepository(),
        remote_change_logs=FakeRemoteChangeLogRepository(),
        uow=FakeUnitOfWork(),
        ttl_minutes=15,
    )

    with pytest.raises(NoRemoteChangeToRollBackError):
        await use_case.execute(
            RollbackFirewallCommandRequest(
                firewall_id=fw.id,
                organization_id=org_id,
                user_id=uuid.uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_rollback_firewall_command_rejects_when_already_rolled_back() -> None:
    from app.domain.entities import RemoteChangeLog

    firewalls = FakeFirewallRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    logs = FakeRemoteChangeLogRepository()
    await logs.create(
        RemoteChangeLog(
            firewall_command_id=uuid.uuid4(),
            firewall_id=fw.id,
            user_id=uuid.uuid4(),
            before_state={"rules": []},
            after_state={"rules": [{"action": "block"}]},
            applied_at=datetime.now(UTC),
            record_hash="deadbeef",
            rolled_back_at=datetime.now(UTC),
            rolled_back_by_user_id=uuid.uuid4(),
        )
    )
    use_case = RollbackFirewallCommand(
        firewalls=firewalls,
        firewall_commands=FakeFirewallCommandRepository(),
        remote_change_logs=logs,
        uow=FakeUnitOfWork(),
        ttl_minutes=15,
    )

    with pytest.raises(ChangeAlreadyRolledBackError):
        await use_case.execute(
            RollbackFirewallCommandRequest(
                firewall_id=fw.id,
                organization_id=org_id,
                user_id=uuid.uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_rollback_firewall_command_creates_pending_command_from_latest_log() -> None:
    from app.domain.entities import RemoteChangeLog

    firewalls = FakeFirewallRepository()
    org_id = uuid.uuid4()
    fw = await firewalls.create(_make_firewall(org_id))
    logs = FakeRemoteChangeLogRepository()
    latest = await logs.create(
        RemoteChangeLog(
            firewall_command_id=uuid.uuid4(),
            firewall_id=fw.id,
            user_id=uuid.uuid4(),
            before_state={"rules": []},
            after_state={"rules": [{"action": "block"}]},
            applied_at=datetime.now(UTC),
            record_hash="deadbeef",
        )
    )
    uow = FakeUnitOfWork()
    use_case = RollbackFirewallCommand(
        firewalls=firewalls,
        firewall_commands=FakeFirewallCommandRepository(),
        remote_change_logs=logs,
        uow=uow,
        ttl_minutes=15,
    )
    user_id = uuid.uuid4()

    command = await use_case.execute(
        RollbackFirewallCommandRequest(
            firewall_id=fw.id,
            organization_id=org_id,
            user_id=user_id,
        )
    )

    assert command.status == "pending_confirmation"
    assert command.command_type == "rollback"
    assert command.user_id == user_id
    assert command.payload["target_change_log_id"] == str(latest.id)
    assert command.payload["restore_state"] == {"rules": []}
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_report_firewall_command_result_rollback_success_marks_original_log() -> None:
    from app.domain.entities import RemoteChangeLog

    commands = FakeFirewallCommandRepository()
    logs = FakeRemoteChangeLogRepository()
    firewall_id = uuid.uuid4()
    user_id = uuid.uuid4()
    original_log = await logs.create(
        RemoteChangeLog(
            firewall_command_id=uuid.uuid4(),
            firewall_id=firewall_id,
            user_id=user_id,
            before_state={"rules": []},
            after_state={"rules": [{"action": "block"}]},
            applied_at=datetime.now(UTC),
            record_hash="deadbeef",
        )
    )
    rollback_command = await commands.create(
        FirewallCommand(
            firewall_id=firewall_id,
            user_id=user_id,
            command_type="rollback",
            payload={
                "target_change_log_id": str(original_log.id),
                "restore_state": {"rules": []},
            },
            status="sent_to_agent",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    uow = FakeUnitOfWork()
    use_case = ReportFirewallCommandResult(
        firewall_commands=commands, remote_change_logs=logs, uow=uow
    )

    await use_case.execute(
        ReportFirewallCommandResultRequest(
            firewall_id=firewall_id,
            command_id=rollback_command.id,
            success=True,
            before_state={"rules": [{"action": "block"}]},
            after_state={"rules": []},
        )
    )

    assert commands.commands[rollback_command.id].status == "applied"
    # A new RemoteChangeLog was appended for the rollback action itself (full audit trail).
    assert len(logs.logs) == 2
    rollback_log = logs.logs[1]
    assert rollback_log.firewall_command_id == rollback_command.id

    # The ORIGINAL log is now marked rolled back.
    updated_original = next(log for log in logs.logs if log.id == original_log.id)
    assert updated_original.rolled_back_at is not None
    assert updated_original.rolled_back_by_user_id == user_id
