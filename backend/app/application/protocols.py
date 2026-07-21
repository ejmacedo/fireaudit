import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.entities import (
    Account,
    AgentToken,
    Finding,
    Firewall,
    Organization,
    RefreshToken,
    Snapshot,
    Subscription,
    User,
    WebhookEvent,
)


class AccountRepository(Protocol):
    async def create(self, account: Account) -> Account: ...
    async def get_by_id(self, account_id: uuid.UUID) -> Account | None: ...


class OrganizationRepository(Protocol):
    async def create(self, organization: Organization) -> Organization: ...
    async def count_active_for_account(self, account_id: uuid.UUID) -> int: ...
    async def list_active_for_account(self, account_id: uuid.UUID) -> list[Organization]: ...


class UserRepository(Protocol):
    async def create(self, user: User) -> User: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...


class RefreshTokenRepository(Protocol):
    async def create(self, token: RefreshToken) -> RefreshToken: ...
    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None: ...
    async def revoke(self, token_id: uuid.UUID) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, plain: str) -> str: ...


class PasswordVerifier(Protocol):
    def verify(self, plain: str, hashed: str) -> bool: ...


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    account_id: uuid.UUID


class TokenService(Protocol):
    def create_access_token(self, user_id: uuid.UUID, account_id: uuid.UUID) -> str: ...
    def decode_access_token(self, token: str) -> AccessTokenClaims: ...
    def generate_refresh_token(self) -> str: ...
    def hash_refresh_token(self, plain: str) -> str: ...


class FirewallRepository(Protocol):
    async def create(self, firewall: Firewall) -> Firewall: ...
    async def get_by_id(self, firewall_id: uuid.UUID) -> Firewall | None: ...
    async def list_active_for_org(
        self, organization_id: uuid.UUID, cursor: uuid.UUID | None, limit: int
    ) -> list[Firewall]: ...
    async def update(self, firewall: Firewall) -> Firewall: ...
    async def record_check_in(
        self, firewall_id: uuid.UUID, pfsense_version: str | None
    ) -> None: ...


class AgentTokenRepository(Protocol):
    async def create(self, token: AgentToken) -> AgentToken: ...
    async def get_active_for_firewall(self, firewall_id: uuid.UUID) -> AgentToken | None: ...
    async def revoke_all_for_firewall(self, firewall_id: uuid.UUID) -> None: ...
    async def get_by_token_hash(self, token_hash: str) -> AgentToken | None: ...


class SnapshotRepository(Protocol):
    async def create(self, snapshot: Snapshot) -> Snapshot: ...
    async def list_queued(self, limit: int = 10) -> list[Snapshot]: ...
    async def update_status(self, snapshot_id: uuid.UUID, status: str) -> None: ...
    async def get_latest_for_firewall(self, firewall_id: uuid.UUID) -> Snapshot | None: ...


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class FindingRepository(Protocol):
    async def create(self, finding: Finding) -> Finding: ...
    async def get_open_by_check_type(
        self, firewall_id: uuid.UUID, check_type: str
    ) -> Finding | None: ...
    async def list_for_firewall(
        self,
        firewall_id: uuid.UUID,
        status: str | None,
        severity: str | None,
        check_type: str | None,
    ) -> list[Finding]: ...
    async def count_open_grouped_by_severity(
        self, firewall_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, int]]: ...
    async def get_by_id(self, finding_id: uuid.UUID) -> Finding | None: ...
    async def update_status(self, finding_id: uuid.UUID, status: str) -> Finding: ...


class AnalysisCheck(Protocol):
    check_type: str

    def run(self, firewall: Firewall, snapshot: Snapshot) -> list[Finding]: ...


class SubscriptionRepository(Protocol):
    async def create(self, subscription: Subscription) -> Subscription: ...
    async def get_by_account_id(self, account_id: uuid.UUID) -> Subscription | None: ...
    async def update_from_stripe_event(
        self,
        account_id: uuid.UUID,
        *,
        tier: str,
        status: str,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        current_period_end: datetime | None = None,
    ) -> Subscription: ...


class WebhookEventRepository(Protocol):
    async def exists(self, event_id: str) -> bool: ...
    async def create(self, event_id: str, event_type: str) -> WebhookEvent: ...


@dataclass(frozen=True)
class CheckoutSession:
    url: str
    session_id: str


@dataclass(frozen=True)
class ParsedWebhookEvent:
    event_id: str
    event_type: str
    data: dict


class PaymentGateway(Protocol):
    def create_checkout_session(
        self,
        *,
        account_id: uuid.UUID,
        customer_email: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession: ...

    def verify_webhook_signature(self, body: bytes, signature: str) -> ParsedWebhookEvent: ...
