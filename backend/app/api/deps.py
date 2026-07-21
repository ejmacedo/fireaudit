from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import AuthContext, get_current_user
from app.application.protocols import PaymentGateway
from app.application.use_cases.create_checkout_session import CreateCheckoutSession
from app.application.use_cases.create_firewall import CreateFirewall
from app.application.use_cases.delete_firewall import DeleteFirewall
from app.application.use_cases.get_firewall import GetFirewall
from app.application.use_cases.get_firewall_rules import GetFirewallRules
from app.application.use_cases.get_firewall_vpn_tunnels import GetFirewallVpnTunnels
from app.application.use_cases.get_subscription import GetSubscription
from app.application.use_cases.ingest_snapshot import IngestSnapshot
from app.application.use_cases.list_findings import ListFindings
from app.application.use_cases.list_firewalls import ListFirewalls
from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.logout_user import LogoutUser
from app.application.use_cases.process_stripe_webhook import ProcessStripeWebhook
from app.application.use_cases.refresh_session import RefreshSession
from app.application.use_cases.register_account import (
    RegisterIndividualAccount,
    RegisterMultiempresaAccount,
)
from app.application.use_cases.rename_firewall import RenameFirewall
from app.application.use_cases.resolve_finding import ResolveFinding
from app.application.use_cases.rotate_token import RotateToken
from app.core.config import settings
from app.infrastructure.database import get_db
from app.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyAgentTokenRepository,
    SqlAlchemyFindingRepository,
    SqlAlchemyFirewallRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemySnapshotRepository,
    SqlAlchemySubscriptionRepository,
    SqlAlchemyUnitOfWork,
    SqlAlchemyUserRepository,
    SqlAlchemyWebhookEventRepository,
)
from app.infrastructure.security import (
    Argon2PasswordHasher,
    Argon2PasswordVerifier,
    build_token_service,
)
from app.infrastructure.stripe_client import StripePaymentGateway


def get_register_individual(
    session: AsyncSession = Depends(get_db),
) -> RegisterIndividualAccount:
    return RegisterIndividualAccount(
        accounts=SqlAlchemyAccountRepository(session),
        organizations=SqlAlchemyOrganizationRepository(session),
        users=SqlAlchemyUserRepository(session),
        subscriptions=SqlAlchemySubscriptionRepository(session),
        hasher=Argon2PasswordHasher(),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_register_multiempresa(
    session: AsyncSession = Depends(get_db),
) -> RegisterMultiempresaAccount:
    return RegisterMultiempresaAccount(
        accounts=SqlAlchemyAccountRepository(session),
        users=SqlAlchemyUserRepository(session),
        subscriptions=SqlAlchemySubscriptionRepository(session),
        hasher=Argon2PasswordHasher(),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_login_user(session: AsyncSession = Depends(get_db)) -> LoginUser:
    return LoginUser(
        users=SqlAlchemyUserRepository(session),
        refresh_tokens=SqlAlchemyRefreshTokenRepository(session),
        verifier=Argon2PasswordVerifier(),
        tokens=build_token_service(),
        uow=SqlAlchemyUnitOfWork(session),
        access_token_ttl_minutes=settings.jwt_access_token_expire_minutes,
        refresh_token_ttl_days=settings.jwt_refresh_token_expire_days,
    )


def get_refresh_session(session: AsyncSession = Depends(get_db)) -> RefreshSession:
    return RefreshSession(
        users=SqlAlchemyUserRepository(session),
        refresh_tokens=SqlAlchemyRefreshTokenRepository(session),
        tokens=build_token_service(),
        uow=SqlAlchemyUnitOfWork(session),
        access_token_ttl_minutes=settings.jwt_access_token_expire_minutes,
        refresh_token_ttl_days=settings.jwt_refresh_token_expire_days,
    )


def get_logout_user(session: AsyncSession = Depends(get_db)) -> LogoutUser:
    return LogoutUser(
        refresh_tokens=SqlAlchemyRefreshTokenRepository(session),
        tokens=build_token_service(),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_create_firewall(session: AsyncSession = Depends(get_db)) -> CreateFirewall:
    return CreateFirewall(
        firewalls=SqlAlchemyFirewallRepository(session),
        agent_tokens=SqlAlchemyAgentTokenRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_list_firewalls(session: AsyncSession = Depends(get_db)) -> ListFirewalls:
    return ListFirewalls(
        firewalls=SqlAlchemyFirewallRepository(session),
        findings=SqlAlchemyFindingRepository(session),
    )


def get_get_firewall(session: AsyncSession = Depends(get_db)) -> GetFirewall:
    return GetFirewall(
        firewalls=SqlAlchemyFirewallRepository(session),
        findings=SqlAlchemyFindingRepository(session),
    )


def get_rename_firewall(session: AsyncSession = Depends(get_db)) -> RenameFirewall:
    return RenameFirewall(
        firewalls=SqlAlchemyFirewallRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_delete_firewall(session: AsyncSession = Depends(get_db)) -> DeleteFirewall:
    return DeleteFirewall(
        firewalls=SqlAlchemyFirewallRepository(session),
        agent_tokens=SqlAlchemyAgentTokenRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_rotate_token(session: AsyncSession = Depends(get_db)) -> RotateToken:
    return RotateToken(
        firewalls=SqlAlchemyFirewallRepository(session),
        agent_tokens=SqlAlchemyAgentTokenRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_ingest_snapshot(session: AsyncSession = Depends(get_db)) -> IngestSnapshot:
    return IngestSnapshot(
        snapshots=SqlAlchemySnapshotRepository(session),
        firewalls=SqlAlchemyFirewallRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_list_findings(session: AsyncSession = Depends(get_db)) -> ListFindings:
    return ListFindings(
        firewalls=SqlAlchemyFirewallRepository(session),
        findings=SqlAlchemyFindingRepository(session),
    )


def get_resolve_finding(session: AsyncSession = Depends(get_db)) -> ResolveFinding:
    return ResolveFinding(
        firewalls=SqlAlchemyFirewallRepository(session),
        findings=SqlAlchemyFindingRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_get_firewall_rules(session: AsyncSession = Depends(get_db)) -> GetFirewallRules:
    return GetFirewallRules(
        firewalls=SqlAlchemyFirewallRepository(session),
        snapshots=SqlAlchemySnapshotRepository(session),
    )


def get_get_firewall_vpn_tunnels(
    session: AsyncSession = Depends(get_db),
) -> GetFirewallVpnTunnels:
    return GetFirewallVpnTunnels(
        firewalls=SqlAlchemyFirewallRepository(session),
        snapshots=SqlAlchemySnapshotRepository(session),
    )


def get_payment_gateway() -> PaymentGateway:
    return StripePaymentGateway(
        secret_key=settings.stripe_secret_key,
        webhook_secret=settings.stripe_webhook_secret,
        price_id_pro=settings.stripe_price_id_pro,
    )


def get_subscription_uc(session: AsyncSession = Depends(get_db)) -> GetSubscription:
    return GetSubscription(subscriptions=SqlAlchemySubscriptionRepository(session))


def get_create_checkout_session(
    session: AsyncSession = Depends(get_db),
) -> CreateCheckoutSession:
    return CreateCheckoutSession(
        subscriptions=SqlAlchemySubscriptionRepository(session),
        gateway=get_payment_gateway(),
    )


def get_process_stripe_webhook(
    session: AsyncSession = Depends(get_db),
) -> ProcessStripeWebhook:
    return ProcessStripeWebhook(
        subscriptions=SqlAlchemySubscriptionRepository(session),
        webhook_events=SqlAlchemyWebhookEventRepository(session),
        gateway=get_payment_gateway(),
        uow=SqlAlchemyUnitOfWork(session),
    )


_TIER_ORDER = {"free": 0, "pro": 1, "premium": 2}


def require_tier(min_tier: str):
    """Dependency factory: returns 403 UPGRADE_REQUIRED if account tier < min_tier.

    Usage: `_: AuthContext = Depends(require_tier("pro"))`.
    """

    if min_tier not in _TIER_ORDER:
        raise ValueError(f"Unknown tier: {min_tier}")

    async def _dep(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        current = _TIER_ORDER.get(ctx.subscription.tier, -1)
        if current < _TIER_ORDER[min_tier]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "UPGRADE_REQUIRED",
                        "message": f"This resource requires the {min_tier} tier.",
                    }
                },
            )
        return ctx

    return _dep
