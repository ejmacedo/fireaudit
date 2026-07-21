"""Fase 8: subscription/billing routes (GET status, POST checkout, POST webhook)."""

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_create_checkout_session,
    get_process_stripe_webhook,
    get_subscription_uc,
)
from app.api.deps_auth import AuthContext, get_current_user
from app.api.errors import error_response
from app.api.schemas.subscription import CheckoutSessionResponse, SubscriptionResponse
from app.application.use_cases.create_checkout_session import (
    CreateCheckoutSession,
    CreateCheckoutSessionRequest,
)
from app.application.use_cases.get_subscription import (
    GetSubscription,
    GetSubscriptionRequest,
)
from app.application.use_cases.process_stripe_webhook import (
    ProcessStripeWebhook,
    ProcessStripeWebhookRequest,
)
from app.core.config import settings
from app.domain.errors import (
    AlreadySubscribedError,
    InvalidWebhookSignatureError,
    SubscriptionNotFoundError,
)

router = APIRouter(prefix="", tags=["subscription"])


@router.get(
    "/subscription",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionResponse,
)
async def get_subscription(
    ctx: AuthContext = Depends(get_current_user),
    use_case: GetSubscription = Depends(get_subscription_uc),
) -> SubscriptionResponse | JSONResponse:
    try:
        sub = await use_case.execute(GetSubscriptionRequest(account_id=ctx.account.id))
    except SubscriptionNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SUBSCRIPTION_NOT_FOUND",
            message="Subscription not found.",
        )
    return SubscriptionResponse(
        tier=sub.tier,
        status=sub.status,
        current_period_end=sub.current_period_end,
    )


@router.post(
    "/subscription/checkout-session",
    status_code=status.HTTP_200_OK,
    response_model=CheckoutSessionResponse,
)
async def create_checkout_session(
    ctx: AuthContext = Depends(get_current_user),
    use_case: CreateCheckoutSession = Depends(get_create_checkout_session),
) -> CheckoutSessionResponse | JSONResponse:
    try:
        result = await use_case.execute(
            CreateCheckoutSessionRequest(
                account_id=ctx.account.id,
                customer_email=ctx.user.email,
                success_url=settings.stripe_success_url,
                cancel_url=settings.stripe_cancel_url,
            )
        )
    except SubscriptionNotFoundError:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SUBSCRIPTION_NOT_FOUND",
            message="Subscription not found.",
        )
    except AlreadySubscribedError:
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="ALREADY_SUBSCRIBED",
            message="Account is already on a paid tier.",
        )
    return CheckoutSessionResponse(url=result.url)


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK, response_model=None)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    use_case: ProcessStripeWebhook = Depends(get_process_stripe_webhook),
) -> dict | JSONResponse:
    if not stripe_signature:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MISSING_SIGNATURE",
            message="Stripe-Signature header is required.",
        )
    body = await request.body()
    try:
        await use_case.execute(ProcessStripeWebhookRequest(body=body, signature=stripe_signature))
    except InvalidWebhookSignatureError:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_SIGNATURE",
            message="Stripe-Signature header did not verify.",
        )
    return {"received": True}
