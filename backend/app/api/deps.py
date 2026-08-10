from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import AuthContext, get_current_user
from app.application.protocols import EmailSender, PaymentGateway
from app.application.use_cases.confirm_firewall_command import ConfirmFirewallCommand
from app.application.use_cases.create_alert_channel import CreateAlertChannel
from app.application.use_cases.create_alert_rule import CreateAlertRule
from app.application.use_cases.create_billing_portal_session import (
    CreateBillingPortalSession,
)
from app.application.use_cases.create_checkout_session import CreateCheckoutSession
from app.application.use_cases.create_firewall import CreateFirewall
from app.application.use_cases.create_firewall_command import CreateFirewallCommand
from app.application.use_cases.delete_firewall import DeleteFirewall
from app.application.use_cases.get_firewall import GetFirewall
from app.application.use_cases.get_firewall_rules import GetFirewallRules
from app.application.use_cases.get_firewall_vpn_tunnels import GetFirewallVpnTunnels
from app.application.use_cases.get_subscription import GetSubscription
from app.application.use_cases.ingest_snapshot import IngestSnapshot
from app.application.use_cases.list_alert_channels import ListAlertChannels
from app.application.use_cases.list_alert_rules import ListAlertRules
from app.application.use_cases.list_findings import ListFindings
from app.application.use_cases.list_firewall_commands import ListFirewallCommands
from app.application.use_cases.list_firewalls import ListFirewalls
from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.logout_user import LogoutUser
from app.application.use_cases.poll_firewall_commands import PollFirewallCommands
from app.application.use_cases.process_stripe_webhook import ProcessStripeWebhook
from app.application.use_cases.refresh_session import RefreshSession
from app.application.use_cases.register_account import (
    RegisterIndividualAccount,
    RegisterMultiempresaAccount,
)
from app.application.use_cases.rename_firewall import RenameFirewall
from app.application.use_cases.report_firewall_command_result import (
    ReportFirewallCommandResult,
)
from app.application.use_cases.request_password_reset import RequestPasswordReset
from app.application.use_cases.reset_password import ResetPassword
from app.application.use_cases.resolve_finding import ResolveFinding
from app.application.use_cases.rollback_firewall_command import RollbackFirewallCommand
from app.application.use_cases.rotate_token import RotateToken
from app.core.config import settings
from app.infrastructure.database import get_db
from app.infrastructure.email_client import LoggingEmailSender, SmtpEmailSender
from app.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyAgentTokenRepository,
    SqlAlchemyAlertChannelRepository,
    SqlAlchemyAlertRuleRepository,
    SqlAlchemyFindingRepository,
    SqlAlchemyFirewallCommandRepository,
    SqlAlchemyFirewallRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyRemoteChangeLogRepository,
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


def get_email_sender() -> EmailSender:
    if settings.smtp_host:
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            from_email=settings.smtp_from_email,
        )
    return LoggingEmailSender()


def get_request_password_reset(
    session: AsyncSession = Depends(get_db),
) -> RequestPasswordReset:
    return RequestPasswordReset(
        users=SqlAlchemyUserRepository(session),
        reset_tokens=SqlAlchemyPasswordResetTokenRepository(session),
        email_sender=get_email_sender(),
        tokens=build_token_service(),
        uow=SqlAlchemyUnitOfWork(session),
        token_ttl_minutes=settings.password_reset_token_ttl_minutes,
        reset_url_base=settings.password_reset_url_base,
    )


def get_reset_password(session: AsyncSession = Depends(get_db)) -> ResetPassword:
    return ResetPassword(
        users=SqlAlchemyUserRepository(session),
        reset_tokens=SqlAlchemyPasswordResetTokenRepository(session),
        refresh_tokens=SqlAlchemyRefreshTokenRepository(session),
        hasher=Argon2PasswordHasher(),
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


def get_create_alert_channel(session: AsyncSession = Depends(get_db)) -> CreateAlertChannel:
    return CreateAlertChannel(
        alert_channels=SqlAlchemyAlertChannelRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_list_alert_channels(session: AsyncSession = Depends(get_db)) -> ListAlertChannels:
    return ListAlertChannels(alert_channels=SqlAlchemyAlertChannelRepository(session))


def get_create_alert_rule(session: AsyncSession = Depends(get_db)) -> CreateAlertRule:
    return CreateAlertRule(
        alert_rules=SqlAlchemyAlertRuleRepository(session),
        alert_channels=SqlAlchemyAlertChannelRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_list_alert_rules(session: AsyncSession = Depends(get_db)) -> ListAlertRules:
    return ListAlertRules(alert_rules=SqlAlchemyAlertRuleRepository(session))


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


def get_create_billing_portal_session(
    session: AsyncSession = Depends(get_db),
) -> CreateBillingPortalSession:
    return CreateBillingPortalSession(
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


def get_create_firewall_command(
    session: AsyncSession = Depends(get_db),
) -> CreateFirewallCommand:
    return CreateFirewallCommand(
        firewalls=SqlAlchemyFirewallRepository(session),
        firewall_commands=SqlAlchemyFirewallCommandRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
        ttl_minutes=settings.firewall_command_ttl_minutes,
    )


def get_confirm_firewall_command(
    session: AsyncSession = Depends(get_db),
) -> ConfirmFirewallCommand:
    return ConfirmFirewallCommand(
        firewalls=SqlAlchemyFirewallRepository(session),
        firewall_commands=SqlAlchemyFirewallCommandRepository(session),
        users=SqlAlchemyUserRepository(session),
        verifier=Argon2PasswordVerifier(),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_list_firewall_commands(
    session: AsyncSession = Depends(get_db),
) -> ListFirewallCommands:
    return ListFirewallCommands(
        firewalls=SqlAlchemyFirewallRepository(session),
        firewall_commands=SqlAlchemyFirewallCommandRepository(session),
    )


def get_rollback_firewall_command(
    session: AsyncSession = Depends(get_db),
) -> RollbackFirewallCommand:
    return RollbackFirewallCommand(
        firewalls=SqlAlchemyFirewallRepository(session),
        firewall_commands=SqlAlchemyFirewallCommandRepository(session),
        remote_change_logs=SqlAlchemyRemoteChangeLogRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
        ttl_minutes=settings.firewall_command_ttl_minutes,
    )


def get_poll_firewall_commands(
    session: AsyncSession = Depends(get_db),
) -> PollFirewallCommands:
    return PollFirewallCommands(
        firewall_commands=SqlAlchemyFirewallCommandRepository(session),
    )


def get_report_firewall_command_result(
    session: AsyncSession = Depends(get_db),
) -> ReportFirewallCommandResult:
    return ReportFirewallCommandResult(
        firewall_commands=SqlAlchemyFirewallCommandRepository(session),
        remote_change_logs=SqlAlchemyRemoteChangeLogRepository(session),
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
