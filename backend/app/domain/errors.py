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


class AgentTokenNotFoundError(DomainError):
    """Agent token not recognized."""


class AgentTokenRevokedError(DomainError):
    """Agent token exists but has been revoked."""


class InvalidHMACSignatureError(DomainError):
    """X-Signature header does not match the expected HMAC-SHA256 of the body."""
