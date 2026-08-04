"""Unit tests (fakes, no DB) for CreateAlertChannel, CreateAlertRule and their list use cases."""

import uuid

import pytest

from app.application.use_cases.create_alert_channel import (
    CreateAlertChannel,
    CreateAlertChannelRequest,
)
from app.application.use_cases.create_alert_rule import CreateAlertRule, CreateAlertRuleRequest
from app.application.use_cases.list_alert_channels import (
    ListAlertChannels,
    ListAlertChannelsRequest,
)
from app.application.use_cases.list_alert_rules import ListAlertRules, ListAlertRulesRequest
from app.domain.entities import AlertChannel, AlertRule
from app.domain.errors import (
    AlertChannelNotFoundError,
    InvalidAlertChannelTypeError,
    InvalidAlertRuleOperatorError,
)


class FakeAlertChannelRepository:
    def __init__(self) -> None:
        self.channels: dict[uuid.UUID, AlertChannel] = {}

    async def create(self, channel: AlertChannel) -> AlertChannel:
        self.channels[channel.id] = channel
        return channel

    async def get_by_id(self, channel_id: uuid.UUID) -> AlertChannel | None:
        return self.channels.get(channel_id)

    async def list_active_for_org(self, organization_id: uuid.UUID) -> list[AlertChannel]:
        return [
            c for c in self.channels.values() if c.organization_id == organization_id and c.active
        ]

    async def list_for_org(self, organization_id: uuid.UUID) -> list[AlertChannel]:
        return [c for c in self.channels.values() if c.organization_id == organization_id]

    async def update(self, channel: AlertChannel) -> AlertChannel:
        self.channels[channel.id] = channel
        return channel

    async def delete(self, channel_id: uuid.UUID) -> None:
        self.channels.pop(channel_id, None)


class FakeAlertRuleRepository:
    def __init__(self) -> None:
        self.rules: dict[uuid.UUID, AlertRule] = {}

    async def create(self, rule: AlertRule) -> AlertRule:
        self.rules[rule.id] = rule
        return rule

    async def get_by_id(self, rule_id: uuid.UUID) -> AlertRule | None:
        return self.rules.get(rule_id)

    async def list_for_org(self, organization_id: uuid.UUID) -> list[AlertRule]:
        return [r for r in self.rules.values() if r.organization_id == organization_id]

    async def update(self, rule: AlertRule) -> AlertRule:
        self.rules[rule.id] = rule
        return rule

    async def delete(self, rule_id: uuid.UUID) -> None:
        self.rules.pop(rule_id, None)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


@pytest.mark.asyncio
async def test_create_alert_channel_rejects_unsupported_type() -> None:
    use_case = CreateAlertChannel(alert_channels=FakeAlertChannelRepository(), uow=FakeUnitOfWork())
    with pytest.raises(InvalidAlertChannelTypeError):
        await use_case.execute(
            CreateAlertChannelRequest(organization_id=uuid.uuid4(), type="slack", config={})
        )


@pytest.mark.asyncio
async def test_create_alert_channel_persists_and_commits() -> None:
    channels = FakeAlertChannelRepository()
    uow = FakeUnitOfWork()
    use_case = CreateAlertChannel(alert_channels=channels, uow=uow)
    org_id = uuid.uuid4()

    channel = await use_case.execute(
        CreateAlertChannelRequest(
            organization_id=org_id, type="email", config={"email": "ops@example.com"}
        )
    )

    assert channel.organization_id == org_id
    assert channel.type == "email"
    assert channel.active is True
    assert uow.commits == 1

    listed = await ListAlertChannels(alert_channels=channels).execute(
        ListAlertChannelsRequest(organization_id=org_id)
    )
    assert listed == [channel]


@pytest.mark.asyncio
async def test_create_alert_rule_rejects_invalid_operator() -> None:
    channels = FakeAlertChannelRepository()
    org_id = uuid.uuid4()
    channel = await channels.create(AlertChannel(organization_id=org_id, type="email", config={}))
    use_case = CreateAlertRule(
        alert_rules=FakeAlertRuleRepository(), alert_channels=channels, uow=FakeUnitOfWork()
    )

    with pytest.raises(InvalidAlertRuleOperatorError):
        await use_case.execute(
            CreateAlertRuleRequest(
                organization_id=org_id,
                metric="open_findings_count",
                operator="not-an-operator",
                threshold=1,
                alert_channel_id=channel.id,
            )
        )


@pytest.mark.asyncio
async def test_create_alert_rule_rejects_channel_from_other_org() -> None:
    channels = FakeAlertChannelRepository()
    other_org_channel = await channels.create(
        AlertChannel(organization_id=uuid.uuid4(), type="email", config={})
    )
    use_case = CreateAlertRule(
        alert_rules=FakeAlertRuleRepository(), alert_channels=channels, uow=FakeUnitOfWork()
    )

    with pytest.raises(AlertChannelNotFoundError):
        await use_case.execute(
            CreateAlertRuleRequest(
                organization_id=uuid.uuid4(),
                metric="open_findings_count",
                operator="gt",
                threshold=1,
                alert_channel_id=other_org_channel.id,
            )
        )


@pytest.mark.asyncio
async def test_create_alert_rule_persists_and_commits() -> None:
    channels = FakeAlertChannelRepository()
    rules = FakeAlertRuleRepository()
    org_id = uuid.uuid4()
    channel = await channels.create(AlertChannel(organization_id=org_id, type="email", config={}))
    uow = FakeUnitOfWork()
    use_case = CreateAlertRule(alert_rules=rules, alert_channels=channels, uow=uow)

    rule = await use_case.execute(
        CreateAlertRuleRequest(
            organization_id=org_id,
            metric="open_findings_count",
            operator="gte",
            threshold=5,
            alert_channel_id=channel.id,
        )
    )

    assert rule.organization_id == org_id
    assert rule.operator == "gte"
    assert rule.alert_channel_id == channel.id
    assert uow.commits == 1

    listed = await ListAlertRules(alert_rules=rules).execute(
        ListAlertRulesRequest(organization_id=org_id)
    )
    assert listed == [rule]
