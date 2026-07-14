from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_login_user,
    get_logout_user,
    get_refresh_session,
    get_register_individual,
    get_register_multiempresa,
)
from app.api.errors import error_response
from app.api.schemas.auth import (
    LoginPayload,
    LogoutPayload,
    RefreshPayload,
    RegisterIndividualPayload,
    RegisterMultiempresaPayload,
    RegisterPayload,
    RegisterResponse,
    TokenResponse,
)
from app.application.use_cases.login_user import (
    LoginRequest,
    LoginUser,
)
from app.application.use_cases.logout_user import LogoutRequest, LogoutUser
from app.application.use_cases.refresh_session import RefreshRequest, RefreshSession
from app.application.use_cases.register_account import (
    RegisterIndividualAccount,
    RegisterIndividualRequest,
    RegisterMultiempresaAccount,
    RegisterMultiempresaRequest,
)
from app.domain.errors import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
)

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


_LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
_LOGIN_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
_login_attempts: dict[str, list[float]] = {}


def _login_rate_limit_check(ip: str, email: str) -> bool:
    """Returns True if within limit, False if the caller exceeded 5 attempts in 15 min.

    In-memory only — single-process rate limiting, adequate for the MVP per
    fase5-seguranca.md §5. Migrate to Redis when the backend scales to multiple
    instances.
    """
    import time

    now = time.monotonic()
    key = f"{ip}:{email}"
    window_start = now - _LOGIN_RATE_LIMIT_WINDOW_SECONDS
    attempts = [t for t in _login_attempts.get(key, []) if t > window_start]
    if len(attempts) >= _LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        _login_attempts[key] = attempts
        return False
    attempts.append(now)
    _login_attempts[key] = attempts
    return True


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginPayload,
    request: Request,
    use_case: LoginUser = Depends(get_login_user),
) -> TokenResponse | JSONResponse:
    from slowapi.util import get_remote_address

    if not _login_rate_limit_check(get_remote_address(request), payload.email):
        return error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
            message="Too many login attempts. Try again later.",
        )

    try:
        result = await use_case.execute(
            LoginRequest(email=payload.email, password=payload.password)
        )
    except InvalidCredentialsError:
        return error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Email or password is incorrect.",
        )

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.access_token_expires_in_seconds,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshPayload,
    use_case: RefreshSession = Depends(get_refresh_session),
) -> TokenResponse | JSONResponse:
    try:
        result = await use_case.execute(RefreshRequest(refresh_token=payload.refresh_token))
    except (InvalidRefreshTokenError, RefreshTokenExpiredError, RefreshTokenRevokedError):
        return error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token is invalid, expired, or revoked.",
        )
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.access_token_expires_in_seconds,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutPayload,
    use_case: LogoutUser = Depends(get_logout_user),
) -> None:
    await use_case.execute(LogoutRequest(refresh_token=payload.refresh_token))
