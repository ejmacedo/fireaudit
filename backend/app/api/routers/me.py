from fastapi import APIRouter, Depends

from app.api.deps_auth import AuthContext, get_current_user
from app.api.schemas.me import MeResponse, OrganizationSummary

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
async def me(ctx: AuthContext = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user_id=ctx.user.id,
        email=ctx.user.email,
        account_id=ctx.account.id,
        account_type=ctx.account.account_type,
        organizations=[OrganizationSummary(id=o.id, name=o.name) for o in ctx.organizations],
    )
