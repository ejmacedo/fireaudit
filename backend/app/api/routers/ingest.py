from fastapi import APIRouter, Depends, Request, status

from app.api.deps import get_ingest_snapshot
from app.api.deps_auth import AgentContext, get_current_agent
from app.api.errors import error_response
from app.api.schemas.ingest import IngestSnapshotResponse, SnapshotPayload
from app.application.use_cases.ingest_snapshot import IngestSnapshot, IngestSnapshotRequest
from app.infrastructure.security import HMACVerifier

router = APIRouter(tags=["ingest"])


@router.post(
    "/snapshot",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestSnapshotResponse,
)
async def ingest_snapshot(
    request: Request,
    payload: SnapshotPayload,
    agent_ctx: AgentContext = Depends(get_current_agent),
    use_case: IngestSnapshot = Depends(get_ingest_snapshot),
) -> IngestSnapshotResponse:
    body_bytes = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not HMACVerifier.verify(agent_ctx.token_hash, body_bytes, signature):
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_SIGNATURE",
            message="X-Signature header does not match body HMAC-SHA256.",
        )
    result = await use_case.execute(
        IngestSnapshotRequest(
            firewall_id=agent_ctx.firewall_id,
            raw_payload=payload.model_dump(mode="json"),
        )
    )
    return IngestSnapshotResponse(snapshot_id=result.snapshot_id, status="queued")
