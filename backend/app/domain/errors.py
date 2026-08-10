class DomainError(Exception):
    """Base class for pure domain errors (no framework/HTTP coupling)."""


class IndividualAccountAlreadyHasOrganizationError(DomainError):
    """An Individual account is structurally limited to exactly one organization."""


class EmailAlreadyRegisteredError(DomainError):
    """The email is already used by another user."""


class InvalidAccountTypeError(DomainError):
    """The account_type is not one of the allowed values."""


class InvalidCredentialsError(DomainError):
    """Email or password does not match a valid user."""


class InvalidRefreshTokenError(DomainError):
    """Refresh token is not recognized."""


class RefreshTokenExpiredError(DomainError):
    """Refresh token exists but has passed its expiration."""


class RefreshTokenRevokedError(DomainError):
    """Refresh token exists but has been revoked (e.g. rotated or logged out)."""


class FirewallNotFoundError(DomainError):
    """Firewall not found or does not belong to the authenticated organization."""


class FirewallNameEmptyError(DomainError):
    """Firewall name cannot be empty."""


class FindingNotFoundError(DomainError):
    """Finding not found or does not belong to the given firewall."""


class AgentTokenNotFoundError(DomainError):
    """Agent token not recognized."""


class AgentTokenRevokedError(DomainError):
    """Agent token exists but has been revoked."""


class InvalidHMACSignatureError(DomainError):
    """X-Signature header does not match the expected HMAC-SHA256 of the body."""


class SubscriptionNotFoundError(DomainError):
    """Subscription row not found for the given account."""


class AlreadySubscribedError(DomainError):
    """Account is already on a paid tier — no checkout session should be created."""


class InvalidWebhookSignatureError(DomainError):
    """Stripe-Signature header did not verify against the configured webhook secret."""


class NoStripeCustomerError(DomainError):
    """Account has no stripe_customer_id yet — it never completed a checkout."""


class InvalidOrExpiredResetTokenError(DomainError):
    """Password reset token is not recognized, already used, or expired."""


class AlertChannelNotFoundError(DomainError):
    """Alert channel not found or does not belong to the given organization."""


class InvalidAlertChannelTypeError(DomainError):
    """The alert channel type is not one of the allowed values."""


class AlertRuleNotFoundError(DomainError):
    """Alert rule not found or does not belong to the given organization."""


class InvalidAlertRuleOperatorError(DomainError):
    """The alert rule operator is not one of the allowed values (gt, gte, lt, lte, eq)."""


class FirewallCommandNotFoundError(DomainError):
    """Firewall command not found or does not belong to the given firewall/organization."""


class InvalidFirewallCommandTypeError(DomainError):
    """The command_type is not one of the allowed values (create_rule, update_rule, delete_rule)."""


class FirewallCommandNotPendingError(DomainError):
    """The command is not in pending_confirmation status (already confirmed/applied/expired)."""


class FirewallCommandExpiredError(DomainError):
    """The command has passed its expires_at timestamp."""


class FirewallCommandNotAwaitingResultError(DomainError):
    """The command is not in sent_to_agent status, so its result cannot be reported."""


class NoRemoteChangeToRollBackError(DomainError):
    """No applied RemoteChangeLog exists yet for this firewall."""


class ChangeAlreadyRolledBackError(DomainError):
    """The most recent RemoteChangeLog for this firewall was already rolled back."""
