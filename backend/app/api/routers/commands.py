import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_confirm_firewall_command,
    get_create_firewall_command,
    get_list_firewall_commands,
    get_rollback_firewall_command,
    require_tier,
)
from app.api.deps_auth import AuthContext
from app.api.errors import error_response
from app.api.schemas.commands import (
    ConfirmFirewallCommandPayload,
    CreateFirewallCommandPayload,
    FirewallCommandResponse,
    ListFirewallCommandsResponse,
)
from app.application.use_cases.confirm_firewall_command import (
    ConfirmFirewallCommand,
    ConfirmFirewallCommandRequest,
)
from app.application.use_cases.create_firewall_command import (
    CreateFirewallCommand,
    CreateFirewallCommandRequest,
)
from app.application.use_cases.list_firewall_commands import (
    ListFirewallCommands,
    ListFirewallCommandsRequest,
)
from app.application.use_cases.rollback_firewall_command import (
    RollbackFirewallCommand,
    RollbackFirewallCommandRequest,
)
from app.domain.entities import FirewallCommand
from app.domain.errors import (
    ChangeAlreadyRolledBackError,
    FirewallCommandExpiredError,
    FirewallCommandNotFoundError,
    FirewallCommandNotPendingError,
    FirewallNotFoundError,
    InvalidCredentialsError,
    InvalidFirewallCommandTypeError,
    NoRemoteChangeToRollBackError,
)

router = APIRouter(prefix="/firewalls", tags=["commands"])


def _org_id_from_ctx(ctx: AuthContext) -> uuid.UUID:
    return next(iter(ctx.organization_ids))


def _command_response(command: FirewallCommand) -> FirewallCommandResponse:
    return FirewallCommandResponse(
        id=command.id,
        firewall_id=command.firewall_id,
        user_id=command.user_id,
        command_type=command.command_type,
        payload=command.payload,
        preview=command.preview,
        status=command.status,
        confirmed_at=command.confirmed_at,
        expires_at=command.expires_at,
        created_at=command.created_at,
        applied_at=command.applied_at,
    )


@router.post(
    "/{firewall_id}/commands",
    status_code=status.HTTP_201_CREATED,
    response_model=FirewallCommandResponse,
)
async def create_firewall_command(
    firewall_id: uuid.UUID,
    payload: CreateFirewallCommandPayload,
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: CreateFirewallCommand = Depends(get_create_firewall_command),
) -> FirewallCommandResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        command = await use_case.execute(
            CreateFirewallCommandRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
                user_id=ctx.user.id,
                command_type=payload.command_type,
                payload=payload.payload,
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    except InvalidFirewallCommandTypeError:
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_COMMAND_TYPE",
            message="The command type is not supported.",
        )
    return _command_response(command)


@router.post(
    "/{firewall_id}/commands/rollback",
    status_code=status.HTTP_201_CREATED,
    response_model=FirewallCommandResponse,
)
async def rollback_firewall_command(
    firewall_id: uuid.UUID,
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: RollbackFirewallCommand = Depends(get_rollback_firewall_command),
) -> FirewallCommandResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        command = await use_case.execute(
            RollbackFirewallCommandRequest(
                firewall_id=firewall_id,
                organization_id=_org_id_from_ctx(ctx),
                user_id=ctx.user.id,
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    except NoRemoteChangeToRollBackError:
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="NO_CHANGE_TO_ROLL_BACK",
            message="There is no applied remote change to roll back for this firewall.",
        )
    except ChangeAlreadyRolledBackError:
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="CHANGE_ALREADY_ROLLED_BACK",
            message="The most recent remote change has already been rolled back.",
        )
    return _command_response(command)


@router.get(
    "/{firewall_id}/commands",
    status_code=status.HTTP_200_OK,
    response_model=ListFirewallCommandsResponse,
)
async def list_firewall_commands(
    firewall_id: uuid.UUID,
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: ListFirewallCommands = Depends(get_list_firewall_commands),
) -> ListFirewallCommandsResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        commands = await use_case.execute(
            ListFirewallCommandsRequest(
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
    return ListFirewallCommandsResponse(commands=[_command_response(c) for c in commands])


@router.post(
    "/{firewall_id}/commands/{command_id}/confirm",
    status_code=status.HTTP_200_OK,
    response_model=FirewallCommandResponse,
)
async def confirm_firewall_command(
    firewall_id: uuid.UUID,
    command_id: uuid.UUID,
    payload: ConfirmFirewallCommandPayload,
    ctx: AuthContext = Depends(require_tier("pro")),
    use_case: ConfirmFirewallCommand = Depends(get_confirm_firewall_command),
) -> FirewallCommandResponse | JSONResponse:
    if not ctx.organization_ids:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    try:
        command = await use_case.execute(
            ConfirmFirewallCommandRequest(
                firewall_id=firewall_id,
                command_id=command_id,
                organization_id=_org_id_from_ctx(ctx),
                user_id=ctx.user.id,
                password=payload.password,
            )
        )
    except FirewallNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_NOT_FOUND",
            message="Firewall not found.",
        )
    except FirewallCommandNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_COMMAND_NOT_FOUND",
            message="Firewall command not found.",
        )
    except FirewallCommandNotPendingError:
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="FIREWALL_COMMAND_NOT_PENDING",
            message="This command has already been confirmed, applied, or is no longer pending.",
        )
    except FirewallCommandExpiredError:
        return error_response(
            status_code=status.HTTP_410_GONE,
            code="FIREWALL_COMMAND_EXPIRED",
            message="This command has expired and can no longer be confirmed.",
        )
    except InvalidCredentialsError:
        return error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Password is incorrect.",
        )
    return _command_response(command)
