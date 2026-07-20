import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_create_firewall,
    get_delete_firewall,
    get_get_firewall,
    get_get_firewall_rules,
    get_get_firewall_vpn_tunnels,
    get_list_findings,
    get_list_firewalls,
    get_rename_firewall,
    get_resolve_finding,
    get_rotate_token,
)
from app.api.deps_auth import AuthContext, get_current_user
from app.api.errors import error_response
from app.api.schemas.findings import (
    FindingResponse,
    ListFindingsResponse,
    ResolveFindingPayload,
)
from app.api.schemas.firewalls import (
    CreateFirewallPayload,
    CreateFirewallResponse,
    FirewallResponse,
    ListFirewallsResponse,
    RenameFirewallPayload,
    RotateTokenResponse,
)
from app.api.schemas.rules import RulesResponse, VpnTunnelsResponse
from app.application.use_cases.create_firewall import CreateFirewall, CreateFirewallRequest
from app.application.use_cases.delete_firewall import DeleteFirewall, DeleteFirewallRequest
from app.application.use_cases.get_firewall import GetFirewall, GetFirewallRequest
from app.application.use_cases.get_firewall_rules import (
    GetFirewallRules,
    GetFirewallRulesRequest,
)
from app.application.use_cases.get_firewall_vpn_tunnels import (
    GetFirewallVpnTunnels,
    GetFirewallVpnTunnelsRequest,
)
from app.application.use_cases.list_findings import ListFindings, ListFindingsRequest
from app.application.use_cases.list_firewalls import ListFirewalls, ListFirewallsRequest
from app.application.use_cases.rename_firewall import RenameFirewall, RenameFirewallRequest
from app.application.use_cases.resolve_finding import ResolveFinding, ResolveFindingRequest
from app.application.use_cases.rotate_token import RotateToken, RotateTokenRequest
from app.domain.entities import Finding, Firewall
from app.domain.errors import (
    FindingNotFoundError,
    FirewallNameEmptyError,
    FirewallNotFoundError,
)

router = APIRouter(prefix="/firewalls", tags=["firewalls"])

_SEVERITIES = ("critical", "high", "medium", "low")


def _severity_counts(counts: dict[str, int] | None) -> dict[str, int]:
    counts = counts or {}
    return {sev: counts.get(sev, 0) for sev in _SEVERITIES}


def _fw_response(
    fw: Firewall, open_findings_by_severity: dict[str, int] | None = None
) -> FirewallResponse:
    return FirewallResponse(
        id=fw.id,
        organization_id=fw.organization_id,
        name=fw.name,
        status=fw.status,
        pfsense_version=fw.pfsense_version,
        last_seen_at=fw.last_seen_at,
        created_at=fw.created_at,
        updated_at=fw.updated_at,
        open_findings_by_severity=_severity_counts(open_findings_by_severity),
    )


def _finding_response(finding: Finding) -> FindingResponse:
    return FindingResponse(
        id=finding.id,
        firewall_id=finding.firewall_id,
        check_type=finding.check_type,
        severity=finding.severity,
        status=finding.status,
        details=finding.details,
        created_at=finding.created_at,
        resolved_at=finding.resolved_at,
    )


def _org_id_from_ctx(ctx: AuthContext) -> uuid.UUID:
    return next(iter(ctx.organization_ids))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateFirewallResponse,
)
async def create_firewall(
    payload: CreateFirewallPayload,
    ctx: AuthContext = Depends(get_current_user),
    use_case: CreateFirewall = Depends(get_create_firewall),
) -> CreateFirewallResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NO_ORGANIZATION",
            message="No organization found for this account.",
        )
    try:
        result = await use_case.execute(
            CreateFirewallRequest(
                organization_id=_org_id_from_ctx(ctx),
                name=payload.name,
            )
        )
    except FirewallNameEmptyError:
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_NAME",
            message="Firewall name cannot be empty.",
        )
    return CreateFirewallResponse(
        firewall=_fw_response(result.firewall),
        agent_token=result.agent_token,
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ListFirewallsResponse,
)
async def list_firewalls(
    cursor: uuid.UUID | None = None,
    limit: int = 20,
    ctx: AuthContext = Depends(get_current_user),
    use_case: ListFirewalls = Depends(get_list_firewalls),
) -> ListFirewallsResponse | JSONResponse:
    if not ctx.organization_ids:
        return ListFirewallsResponse(firewalls=[], next_cursor=None)
    result = await use_case.execute(
        ListFirewallsRequest(
            organization_id=_org_id_from_ctx(ctx),
            cursor=cursor,
            limit=limit,
        )
    )
    return ListFirewallsResponse(
        firewalls=[
            _fw_response(fw, result.open_findings_by_severity.get(fw.id)) for fw in result.firewalls
        ],
        next_cursor=result.next_cursor,
    )


@router.get(
    "/{firewall_id}",
    status_code=status.HTTP_200_OK,
    response_model=FirewallResponse,
)
async def get_firewall(
    firewall_id: uuid.UUID,
    ctx: AuthContext = Depends(get_current_user),
    use_case: GetFirewall = Depends(get_get_firewall),
) -> FirewallResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        result = await use_case.execute(
            GetFirewallRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    return _fw_response(result.firewall, result.open_findings_by_severity)


@router.patch(
    "/{firewall_id}",
    status_code=status.HTTP_200_OK,
    response_model=FirewallResponse,
)
async def rename_firewall(
    firewall_id: uuid.UUID,
    payload: RenameFirewallPayload,
    ctx: AuthContext = Depends(get_current_user),
    use_case: RenameFirewall = Depends(get_rename_firewall),
) -> FirewallResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        fw = await use_case.execute(
            RenameFirewallRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
                name=payload.name,
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    except FirewallNameEmptyError:
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_NAME",
            message="Firewall name cannot be empty.",
        )
    return _fw_response(fw)


@router.delete(
    "/{firewall_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_firewall(
    firewall_id: uuid.UUID,
    ctx: AuthContext = Depends(get_current_user),
    use_case: DeleteFirewall = Depends(get_delete_firewall),
) -> None:
    if not ctx.organization_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "FIREWALL_NOT_FOUND", "message": "Firewall not found."}},
        )
    try:
        await use_case.execute(
            DeleteFirewallRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
            )
        )
    except FirewallNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "FIREWALL_NOT_FOUND", "message": "Firewall not found."}},
        )


@router.post(
    "/{firewall_id}/rotate-token",
    status_code=status.HTTP_200_OK,
    response_model=RotateTokenResponse,
)
async def rotate_token(
    firewall_id: uuid.UUID,
    ctx: AuthContext = Depends(get_current_user),
    use_case: RotateToken = Depends(get_rotate_token),
) -> RotateTokenResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        result = await use_case.execute(
            RotateTokenRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    return RotateTokenResponse(agent_token=result.agent_token)


@router.get(
    "/{firewall_id}/findings",
    status_code=status.HTTP_200_OK,
    response_model=ListFindingsResponse,
)
async def list_findings(
    firewall_id: uuid.UUID,
    status_filter: str | None = None,
    severity: str | None = None,
    check_type: str | None = None,
    ctx: AuthContext = Depends(get_current_user),
    use_case: ListFindings = Depends(get_list_findings),
) -> ListFindingsResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        findings = await use_case.execute(
            ListFindingsRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
                status=status_filter,
                severity=severity,
                check_type=check_type,
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    return ListFindingsResponse(findings=[_finding_response(f) for f in findings])


@router.patch(
    "/{firewall_id}/findings/{finding_id}",
    status_code=status.HTTP_200_OK,
    response_model=FindingResponse,
)
async def resolve_finding(
    firewall_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: ResolveFindingPayload,
    ctx: AuthContext = Depends(get_current_user),
    use_case: ResolveFinding = Depends(get_resolve_finding),
) -> FindingResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        finding = await use_case.execute(
            ResolveFindingRequest(
                firewall_id=firewall_id,
                finding_id=finding_id,
                organization_id=_org_id_from_ctx(ctx),
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    except FindingNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FINDING_NOT_FOUND",
            message="Finding not found.",
        )
    return _finding_response(finding)


@router.get(
    "/{firewall_id}/rules",
    status_code=status.HTTP_200_OK,
    response_model=RulesResponse,
)
async def get_firewall_rules(
    firewall_id: uuid.UUID,
    ctx: AuthContext = Depends(get_current_user),
    use_case: GetFirewallRules = Depends(get_get_firewall_rules),
) -> RulesResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        rules = await use_case.execute(
            GetFirewallRulesRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    return RulesResponse(rules=rules)


@router.get(
    "/{firewall_id}/vpn-tunnels",
    status_code=status.HTTP_200_OK,
    response_model=VpnTunnelsResponse,
)
async def get_firewall_vpn_tunnels(
    firewall_id: uuid.UUID,
    ctx: AuthContext = Depends(get_current_user),
    use_case: GetFirewallVpnTunnels = Depends(get_get_firewall_vpn_tunnels),
) -> VpnTunnelsResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        vpn_tunnels = await use_case.execute(
            GetFirewallVpnTunnelsRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    return VpnTunnelsResponse(vpn_tunnels=vpn_tunnels)
