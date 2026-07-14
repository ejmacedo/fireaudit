class DomainError(Exception):
    """Base class for pure domain errors (no framework/HTTP coupling)."""


class IndividualAccountAlreadyHasOrganizationError(DomainError):
    """An Individual account is structurally limited to exactly one organization."""


class EmailAlreadyRegisteredError(DomainError):
    """The email is already used by another user."""


class InvalidAccountTypeError(DomainError):
    """The account_type is not one of the allowed values."""
