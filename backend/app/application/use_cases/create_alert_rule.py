import uuid
from dataclasses import dataclass

from app.application.protocols import AlertChannelRepository, AlertRuleRepository, UnitOfWork
from app.domain.entities import AlertRule
from app.domain.errors import AlertChannelNotFoundError, InvalidAlertRuleOperatorError

ALLOWED_ALERT_RULE_OPERATORS = frozenset({"gt", "gte", "lt", "lte", "eq"})


@dataclass(frozen=True)
class CreateAlertRuleRequest:
    organization_id: uuid.UUID
    metric: str
    operator: str
    threshold: float
    alert_channel_id: uuid.UUID
    firewall_id: uuid.UUID | None = None
    duration_minutes: int = 0
    created_by_user_id: uuid.UUID | None = None


class CreateAlertRule:
    def __init__(
        self,
        alert_rules: AlertRuleRepository,
        alert_channels: AlertChannelRepository,
        uow: UnitOfWork,
    ) -> None:
        self._alert_rules = alert_rules
        self._alert_channels = alert_channels
        self._uow = uow

    async def execute(self, request: CreateAlertRuleRequest) -> AlertRule:
        if request.operator not in ALLOWED_ALERT_RULE_OPERATORS:
            raise InvalidAlertRuleOperatorError

        channel = await self._alert_channels.get_by_id(request.alert_channel_id)
        if channel is None or channel.organization_id != request.organization_id:
            raise AlertChannelNotFoundError

        rule = AlertRule(
            organization_id=request.organization_id,
            firewall_id=request.firewall_id,
            metric=request.metric,
            operator=request.operator,
            threshold=request.threshold,
            duration_minutes=request.duration_minutes,
            alert_channel_id=request.alert_channel_id,
            created_by_user_id=request.created_by_user_id,
        )
        rule = await self._alert_rules.create(rule)
        await self._uow.commit()
        return rule
