import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_create_firewall,
    get_delete_firewall,
    get_get_firewall,
    get_list_firewalls,
    get_rename_firewall,
    get_rotate_token,
)
from app.api.deps_auth import AuthContext, get_current_user
from app.api.errors import error_response
from app.api.schemas.firewalls import (
    CreateFirewallPayload,
    CreateFirewallResponse,
    FirewallResponse,
    ListFirewallsResponse,
    RenameFirewallPayload,
    RotateTokenResponse,
)
from app.application.use_cases.create_firewall import CreateFirewall, CreateFirewallRequest
from app.application.use_cases.delete_firewall import DeleteFirewall, DeleteFirewallRequest
from app.application.use_cases.get_firewall import GetFirewall, GetFirewallRequest
from app.application.use_cases.list_firewalls import ListFirewalls, ListFirewallsRequest
from app.application.use_cases.rename_firewall import RenameFirewall, RenameFirewallRequest
from app.application.use_cases.rotate_token import RotateToken, RotateTokenRequest
from app.domain.entities import Firewall
from app.domain.errors import FirewallNameEmptyError, FirewallNotFoundError

router = APIRouter(prefix="/firewalls", tags=["firewalls"])


def _fw_response(fw: Firewall) -> FirewallResponse:
    return FirewallResponse(
        id=fw.id,
        organization_id=fw.organization_id,
        name=fw.name,
        status=fw.status,
        pfsense_version=fw.pfsense_version,
        last_seen_at=fw.last_seen_at,
        created_at=fw.created_at,
        updated_at=fw.updated_at,
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
        firewalls=[_fw_response(fw) for fw in result.firewalls],
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
        fw = await use_case.execute(
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
    return _fw_response(fw)


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
