import uuid
from dataclasses import dataclass

from app.application.protocols import AlertChannelRepository, UnitOfWork
from app.domain.entities import AlertChannel
from app.domain.errors import InvalidAlertChannelTypeError

ALLOWED_ALERT_CHANNEL_TYPES = frozenset({"email"})


@dataclass(frozen=True)
class CreateAlertChannelRequest:
    organization_id: uuid.UUID
    type: str
    config: dict


class CreateAlertChannel:
    def __init__(self, alert_channels: AlertChannelRepository, uow: UnitOfWork) -> None:
        self._alert_channels = alert_channels
        self._uow = uow

    async def execute(self, request: CreateAlertChannelRequest) -> AlertChannel:
        if request.type not in ALLOWED_ALERT_CHANNEL_TYPES:
            raise InvalidAlertChannelTypeError

        channel = AlertChannel(
            organization_id=request.organization_id,
            type=request.type,
            config=request.config,
        )
        channel = await self._alert_channels.create(channel)
        await self._uow.commit()
        return channel
