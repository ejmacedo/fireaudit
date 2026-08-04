"""Unit test (fakes, no DB) for the DeliverAlerts use case."""

import uuid

import pytest

from app.application.use_cases.deliver_alerts import DeliverAlerts, DeliverAlertsRequest
from app.domain.entities import AlertChannel, AlertDelivery, Finding, Firewall


class FakeAlertChannelRepository:
    def __init__(self, channels: list[AlertChannel]) -> None:
        self._channels = channels

    async def list_active_for_org(self, organization_id: uuid.UUID) -> list[AlertChannel]:
        return [c for c in self._channels if c.organization_id == organization_id and c.active]


class FakeAlertDeliveryRepository:
    def __init__(self) -> None:
        self.created: list[AlertDelivery] = []
        self.updated: list[tuple[uuid.UUID, str, str | None]] = []

    async def create(self, delivery: AlertDelivery) -> AlertDelivery:
        self.created.append(delivery)
        return delivery

    async def update_status(
        self, delivery_id: uuid.UUID, *, status: str, error: str | None = None
    ) -> AlertDelivery:
        self.updated.append((delivery_id, status, error))
        for d in self.created:
            if d.id == delivery_id:
                d.status = status
                d.error = error
                return d
        raise ValueError("delivery not found")


class FakeEmailSender:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[dict] = []

    async def send(self, *, to: str, subject: str, body_text: str) -> None:
        if self.fail:
            raise RuntimeError("smtp down")
        self.sent.append({"to": to, "subject": subject, "body_text": body_text})


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


def _firewall(org_id: uuid.UUID) -> Firewall:
    return Firewall(id=uuid.uuid4(), organization_id=org_id, name="pf-test")


def _finding(fw_id: uuid.UUID) -> Finding:
    return Finding(
        firewall_id=fw_id,
        snapshot_id=uuid.uuid4(),
        check_type="agent_offline",
        severity="high",
        details={},
    )


@pytest.mark.asyncio
async def test_delivers_to_all_active_channels_of_org() -> None:
    org_id = uuid.uuid4()
    fw = _firewall(org_id)
    channels = [
        AlertChannel(organization_id=org_id, type="email", config={"email": "a@example.com"}),
        AlertChannel(organization_id=org_id, type="email", config={"email": "b@example.com"}),
        AlertChannel(
            organization_id=org_id, type="email", config={"email": "c@example.com"}, active=False
        ),
    ]
    deliveries = FakeAlertDeliveryRepository()
    email_sender = FakeEmailSender()
    use_case = DeliverAlerts(
        alert_channels=FakeAlertChannelRepository(channels),
        alert_deliveries=deliveries,
        email_sender=email_sender,
        uow=FakeUnitOfWork(),
    )
    finding = _finding(fw.id)

    delivered = await use_case.execute(DeliverAlertsRequest(firewall=fw, findings=[finding]))

    assert delivered == 2
    assert len(email_sender.sent) == 2
    assert {d["to"] for d in email_sender.sent} == {"a@example.com", "b@example.com"}
    assert all(status == "sent" for _, status, _ in deliveries.updated)


@pytest.mark.asyncio
async def test_no_channels_means_no_deliveries() -> None:
    org_id = uuid.uuid4()
    fw = _firewall(org_id)
    use_case = DeliverAlerts(
        alert_channels=FakeAlertChannelRepository([]),
        alert_deliveries=FakeAlertDeliveryRepository(),
        email_sender=FakeEmailSender(),
        uow=FakeUnitOfWork(),
    )
    finding = _finding(fw.id)

    delivered = await use_case.execute(DeliverAlertsRequest(firewall=fw, findings=[finding]))

    assert delivered == 0


@pytest.mark.asyncio
async def test_no_findings_means_no_deliveries_even_with_channels() -> None:
    org_id = uuid.uuid4()
    fw = _firewall(org_id)
    channels = [AlertChannel(organization_id=org_id, type="email", config={"email": "a@x.com"})]
    use_case = DeliverAlerts(
        alert_channels=FakeAlertChannelRepository(channels),
        alert_deliveries=FakeAlertDeliveryRepository(),
        email_sender=FakeEmailSender(),
        uow=FakeUnitOfWork(),
    )

    delivered = await use_case.execute(DeliverAlertsRequest(firewall=fw, findings=[]))

    assert delivered == 0


@pytest.mark.asyncio
async def test_send_failure_marks_delivery_failed_without_raising() -> None:
    org_id = uuid.uuid4()
    fw = _firewall(org_id)
    channels = [AlertChannel(organization_id=org_id, type="email", config={"email": "a@x.com"})]
    deliveries = FakeAlertDeliveryRepository()
    use_case = DeliverAlerts(
        alert_channels=FakeAlertChannelRepository(channels),
        alert_deliveries=deliveries,
        email_sender=FakeEmailSender(fail=True),
        uow=FakeUnitOfWork(),
    )
    finding = _finding(fw.id)

    delivered = await use_case.execute(DeliverAlertsRequest(firewall=fw, findings=[finding]))

    assert delivered == 1
    assert deliveries.updated[0][1] == "failed"
    assert deliveries.updated[0][2] == "smtp down"


@pytest.mark.asyncio
async def test_unsupported_channel_type_marks_delivery_failed() -> None:
    org_id = uuid.uuid4()
    fw = _firewall(org_id)
    channels = [AlertChannel(organization_id=org_id, type="slack", config={})]
    deliveries = FakeAlertDeliveryRepository()
    use_case = DeliverAlerts(
        alert_channels=FakeAlertChannelRepository(channels),
        alert_deliveries=deliveries,
        email_sender=FakeEmailSender(),
        uow=FakeUnitOfWork(),
    )
    finding = _finding(fw.id)

    delivered = await use_case.execute(DeliverAlertsRequest(firewall=fw, findings=[finding]))

    assert delivered == 1
    assert deliveries.updated[0][1] == "failed"
    assert "unsupported channel type" in deliveries.updated[0][2]


@pytest.mark.asyncio
async def test_missing_email_in_config_marks_delivery_failed() -> None:
    org_id = uuid.uuid4()
    fw = _firewall(org_id)
    channels = [AlertChannel(organization_id=org_id, type="email", config={})]
    deliveries = FakeAlertDeliveryRepository()
    use_case = DeliverAlerts(
        alert_channels=FakeAlertChannelRepository(channels),
        alert_deliveries=deliveries,
        email_sender=FakeEmailSender(),
        uow=FakeUnitOfWork(),
    )
    finding = _finding(fw.id)

    delivered = await use_case.execute(DeliverAlertsRequest(firewall=fw, findings=[finding]))

    assert delivered == 1
    assert deliveries.updated[0][1] == "failed"
    assert "missing 'email'" in deliveries.updated[0][2]
