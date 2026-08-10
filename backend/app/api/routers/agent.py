import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.deps import get_poll_firewall_commands, get_report_firewall_command_result
from app.api.deps_auth import AgentContext, get_current_agent
from app.api.errors import error_response
from app.api.schemas.commands import (
    AgentFirewallCommandResponse,
    ListAgentFirewallCommandsResponse,
    ReportFirewallCommandResultPayload,
)
from app.application.use_cases.poll_firewall_commands import (
    PollFirewallCommands,
    PollFirewallCommandsRequest,
)
from app.application.use_cases.report_firewall_command_result import (
    ReportFirewallCommandResult,
    ReportFirewallCommandResultRequest,
)
from app.domain.errors import (
    FirewallCommandNotAwaitingResultError,
    FirewallCommandNotFoundError,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get(
    "/commands",
    status_code=status.HTTP_200_OK,
    response_model=ListAgentFirewallCommandsResponse,
)
async def poll_commands(
    agent_ctx: AgentContext = Depends(get_current_agent),
    use_case: PollFirewallCommands = Depends(get_poll_firewall_commands),
) -> ListAgentFirewallCommandsResponse:
    commands = await use_case.execute(
        PollFirewallCommandsRequest(firewall_id=agent_ctx.firewall_id)
    )
    return ListAgentFirewallCommandsResponse(
        commands=[
            AgentFirewallCommandResponse(id=c.id, command_type=c.command_type, payload=c.payload)
            for c in commands
        ]
    )


@router.post(
    "/commands/{command_id}/result",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def report_command_result(
    command_id: uuid.UUID,
    payload: ReportFirewallCommandResultPayload,
    agent_ctx: AgentContext = Depends(get_current_agent),
    use_case: ReportFirewallCommandResult = Depends(get_report_firewall_command_result),
) -> None | JSONResponse:
    try:
        await use_case.execute(
            ReportFirewallCommandResultRequest(
                firewall_id=agent_ctx.firewall_id,
                command_id=command_id,
                success=payload.success,
                before_state=payload.before_state,
                after_state=payload.after_state,
                error=payload.error,
            )
        )
    except FirewallCommandNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FIREWALL_COMMAND_NOT_FOUND",
            message="Firewall command not found.",
        )
    except FirewallCommandNotAwaitingResultError:
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="FIREWALL_COMMAND_NOT_AWAITING_RESULT",
            message="This command is not awaiting a result from the agent.",
        )
    return None
