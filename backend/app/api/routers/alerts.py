import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_create_alert_channel,
    get_create_alert_rule,
    get_list_alert_channels,
    get_list_alert_rules,
    require_tier,
)
from app.api.deps_auth import AuthContext
from app.api.errors import error_response
from app.api.schemas.alerts import (
    AlertChannelResponse,
    AlertRuleResponse,
    CreateAlertChannelPayload,
    CreateAlertRulePayload,
    ListAlertChannelsResponse,
    ListAlertRulesResponse,
)
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

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _org_id_from_ctx(ctx: AuthContext) -> uuid.UUID:
    return next(iter(ctx.organization_ids))


def _channel_response(channel: AlertChannel) -> AlertChannelResponse:
    return AlertChannelResponse(
        id=channel.id,
        organization_id=channel.organization_id,
        type=channel.type,
        config=channel.config,
        active=channel.active,
    )


def _rule_response(rule: AlertRule) -> AlertRuleResponse:
    return AlertRuleResponse(
        id=rule.id,
        organization_id=rule.organization_id,
        firewall_id=rule.firewall_id,
        metric=rule.metric,
        operator=rule.operator,
        threshold=rule.threshold,
        duration_minutes=rule.duration_minutes,
        alert_channel_id=rule.alert_channel_id,
        active=rule.active,
        created_by_user_id=rule.created_by_user_id,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.post(
    "/channels",
    status_code=status.HTTP_201_CREATED,
    response_model=AlertChannelResponse,
)
async def create_alert_channel(
    payload: CreateAlertChannelPayload,
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: CreateAlertChannel = Depends(get_create_alert_channel),
) -> AlertChannelResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NO_ORGANIZATION",
            message="No organization found for this account.",
        )
    try:
        channel = await use_case.execute(
            CreateAlertChannelRequest(
                organization_id=_org_id_from_ctx(ctx),
                type=payload.type,
                config=payload.config,
            )
        )
    except InvalidAlertChannelTypeError:
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_ALERT_CHANNEL_TYPE",
            message="The alert channel type is not supported.",
        )
    return _channel_response(channel)


@router.get(
    "/channels",
    status_code=status.HTTP_200_OK,
    response_model=ListAlertChannelsResponse,
)
async def list_alert_channels(
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: ListAlertChannels = Depends(get_list_alert_channels),
) -> ListAlertChannelsResponse:
    if not ctx.organization_ids:
        return ListAlertChannelsResponse(alert_channels=[])
    channels = await use_case.execute(
        ListAlertChannelsRequest(organization_id=_org_id_from_ctx(ctx))
    )
    return ListAlertChannelsResponse(alert_channels=[_channel_response(c) for c in channels])


@router.post(
    "/rules",
    status_code=status.HTTP_201_CREATED,
    response_model=AlertRuleResponse,
)
async def create_alert_rule(
    payload: CreateAlertRulePayload,
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: CreateAlertRule = Depends(get_create_alert_rule),
) -> AlertRuleResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NO_ORGANIZATION",
            message="No organization found for this account.",
        )
    try:
        rule = await use_case.execute(
            CreateAlertRuleRequest(
                organization_id=_org_id_from_ctx(ctx),
                metric=payload.metric,
                operator=payload.operator,
                threshold=payload.threshold,
                alert_channel_id=payload.alert_channel_id,
                firewall_id=payload.firewall_id,
                duration_minutes=payload.duration_minutes,
                created_by_user_id=ctx.user.id,
            )
        )
    except InvalidAlertRuleOperatorError:
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_ALERT_RULE_OPERATOR",
            message="The alert rule operator is not supported.",
        )
    except AlertChannelNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ALERT_CHANNEL_NOT_FOUND",
            message="Alert channel not found.",
        )
    return _rule_response(rule)


@router.get(
    "/rules",
    status_code=status.HTTP_200_OK,
    response_model=ListAlertRulesResponse,
)
async def list_alert_rules(
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: ListAlertRules = Depends(get_list_alert_rules),
) -> ListAlertRulesResponse:
    if not ctx.organization_ids:
        return ListAlertRulesResponse(alert_rules=[])
    rules = await use_case.execute(ListAlertRulesRequest(organization_id=_org_id_from_ctx(ctx)))
    return ListAlertRulesResponse(alert_rules=[_rule_response(r) for r in rules])
