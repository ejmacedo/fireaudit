from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.deps import get_register_individual, get_register_multiempresa
from app.api.errors import error_response
from app.api.schemas.auth import (
    RegisterIndividualPayload,
    RegisterMultiempresaPayload,
    RegisterPayload,
    RegisterResponse,
)
from app.application.use_cases.register_account import (
    RegisterIndividualAccount,
    RegisterIndividualRequest,
    RegisterMultiempresaAccount,
    RegisterMultiempresaRequest,
)
from app.domain.errors import EmailAlreadyRegisteredError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
)
async def register(
    payload: RegisterPayload,
    register_individual: RegisterIndividualAccount = Depends(get_register_individual),
    register_multiempresa: RegisterMultiempresaAccount = Depends(get_register_multiempresa),
) -> RegisterResponse | JSONResponse:
    try:
        if isinstance(payload, RegisterIndividualPayload):
            result = await register_individual.execute(
                RegisterIndividualRequest(
                    email=payload.email,
                    password=payload.password,
                    organization_name=payload.organization_name,
                )
            )
        else:
            assert isinstance(payload, RegisterMultiempresaPayload)
            result = await register_multiempresa.execute(
                RegisterMultiempresaRequest(
                    email=payload.email,
                    password=payload.password,
                    tax_id=payload.tax_id,
                )
            )
    except EmailAlreadyRegisteredError:
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="EMAIL_ALREADY_REGISTERED",
            message="An account with this email already exists.",
        )

    return RegisterResponse(
        account_id=result.account_id,
        user_id=result.user_id,
        organization_id=result.organization_id,
    )
