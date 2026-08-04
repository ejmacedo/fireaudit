import uuid
from dataclasses import dataclass

from app.application.protocols import AlertChannelRepository
from app.domain.entities import AlertChannel


@dataclass(frozen=True)
class ListAlertChannelsRequest:
    organization_id: uuid.UUID


class ListAlertChannels:
    def __init__(self, alert_channels: AlertChannelRepository) -> None:
        self._alert_channels = alert_channels

    async def execute(self, request: ListAlertChannelsRequest) -> list[AlertChannel]:
        return await self._alert_channels.list_for_org(request.organization_id)
