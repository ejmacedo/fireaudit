import logging
from dataclasses import dataclass, field

from app.application.protocols import (
    AlertChannelRepository,
    AlertDeliveryRepository,
    EmailSender,
    UnitOfWork,
)
from app.domain.entities import AlertChannel, AlertDelivery, Finding, Firewall

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliverAlertsRequest:
    firewall: Firewall
    findings: list[Finding] = field(default_factory=list)


class DeliverAlerts:
    """Notifies every active AlertChannel of the firewall's organization for each new Finding.

    Delivery is best-effort: a failed send updates the AlertDelivery row's status/error
    but never raises, so it can never break the snapshot-processing pipeline that calls it.
    """

    def __init__(
        self,
        alert_channels: AlertChannelRepository,
        alert_deliveries: AlertDeliveryRepository,
        email_sender: EmailSender,
        uow: UnitOfWork,
    ) -> None:
        self._alert_channels = alert_channels
        self._alert_deliveries = alert_deliveries
        self._email_sender = email_sender
        self._uow = uow

    async def execute(self, request: DeliverAlertsRequest) -> int:
        if not request.findings:
            return 0

        channels = await self._alert_channels.list_active_for_org(request.firewall.organization_id)
        if not channels:
            return 0

        delivered = 0
        for finding in request.findings:
            for channel in channels:
                delivery = await self._alert_deliveries.create(
                    AlertDelivery(finding_id=finding.id, alert_channel_id=channel.id)
                )
                await self._send_one(delivery, channel, request.firewall, finding)
                delivered += 1

        await self._uow.commit()
        return delivered

    async def _send_one(
        self, delivery: AlertDelivery, channel: AlertChannel, firewall: Firewall, finding: Finding
    ) -> None:
        if channel.type != "email":
            await self._alert_deliveries.update_status(
                delivery.id, status="failed", error=f"unsupported channel type: {channel.type}"
            )
            return

        to_email = channel.config.get("email")
        if not to_email:
            await self._alert_deliveries.update_status(
                delivery.id, status="failed", error="channel config missing 'email'"
            )
            return

        subject = f"[FireAudit] New {finding.severity} finding on {firewall.name}"
        body_text = (
            f"A new finding was detected on firewall '{firewall.name}'.\n\n"
            f"Check type: {finding.check_type}\n"
            f"Severity: {finding.severity}\n"
            f"Details: {finding.details}\n"
        )
        try:
            await self._email_sender.send(to=to_email, subject=subject, body_text=body_text)
        except Exception as exc:
            logger.exception("Failed to deliver alert %s via channel %s", delivery.id, channel.id)
            await self._alert_deliveries.update_status(delivery.id, status="failed", error=str(exc))
        else:
            await self._alert_deliveries.update_status(delivery.id, status="sent")
