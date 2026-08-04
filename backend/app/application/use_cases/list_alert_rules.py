import uuid
from dataclasses import dataclass

from app.application.protocols import AlertRuleRepository
from app.domain.entities import AlertRule


@dataclass(frozen=True)
class ListAlertRulesRequest:
    organization_id: uuid.UUID


class ListAlertRules:
    def __init__(self, alert_rules: AlertRuleRepository) -> None:
        self._alert_rules = alert_rules

    async def execute(self, request: ListAlertRulesRequest) -> list[AlertRule]:
        return await self._alert_rules.list_for_org(request.organization_id)
