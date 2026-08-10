import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    Account,
    AgentToken,
    AlertChannel,
    AlertDelivery,
    AlertRule,
    Finding,
    Firewall,
    FirewallCommand,
    Organization,
    PasswordResetToken,
    RefreshToken,
    RemoteChangeLog,
    Snapshot,
    Subscription,
    User,
    WebhookEvent,
)
from app.infrastructure import models


def _refresh_token_from_orm(row: models.RefreshToken) -> RefreshToken:
    return RefreshToken(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


def _password_reset_token_from_orm(row: models.PasswordResetToken) -> PasswordResetToken:
    return PasswordResetToken(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
        created_at=row.created_at,
    )


def _account_from_orm(row: models.Account) -> Account:
    return Account(
        id=row.id,
        account_type=row.account_type,
        tax_id=row.tax_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _organization_from_orm(row: models.Organization) -> Organization:
    return Organization(
        id=row.id,
        account_id=row.account_id,
        name=row.name,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _user_from_orm(row: models.User) -> User:
    return User(
        id=row.id,
        account_id=row.account_id,
        email=row.email,
        password_hash=row.password_hash,
        role=row.role,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, account: Account) -> Account:
        row = models.Account(
            id=account.id,
            account_type=account.account_type,
            tax_id=account.tax_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _account_from_orm(row)

    async def get_by_id(self, account_id: uuid.UUID) -> Account | None:
        row = await self._session.get(models.Account, account_id)
        return _account_from_orm(row) if row else None


class SqlAlchemyOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, organization: Organization) -> Organization:
        row = models.Organization(
            id=organization.id,
            account_id=organization.account_id,
            name=organization.name,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _organization_from_orm(row)

    async def count_active_for_account(self, account_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(models.Organization)
            .where(
                models.Organization.account_id == account_id,
                models.Organization.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_active_for_account(self, account_id: uuid.UUID) -> list[Organization]:
        stmt = select(models.Organization).where(
            models.Organization.account_id == account_id,
            models.Organization.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return [_organization_from_orm(row) for row in result.scalars().all()]


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        row = models.User(
            id=user.id,
            account_id=user.account_id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _user_from_orm(row)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(models.User).where(models.User.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _user_from_orm(row) if row else None

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        row = await self._session.get(models.User, user_id)
        return _user_from_orm(row) if row else None

    async def update_password_hash(self, user_id: uuid.UUID, password_hash: str) -> None:
        stmt = (
            update(models.User).where(models.User.id == user_id).values(password_hash=password_hash)
        )
        await self._session.execute(stmt)


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, token: RefreshToken) -> RefreshToken:
        row = models.RefreshToken(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _refresh_token_from_orm(row)

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(models.RefreshToken).where(models.RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _refresh_token_from_orm(row) if row else None

    async def revoke(self, token_id: uuid.UUID) -> None:
        stmt = (
            update(models.RefreshToken)
            .where(models.RefreshToken.id == token_id)
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = (
            update(models.RefreshToken)
            .where(models.RefreshToken.user_id == user_id)
            .where(models.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)


class SqlAlchemyPasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        row = models.PasswordResetToken(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            used_at=token.used_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _password_reset_token_from_orm(row)

    async def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        stmt = select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == token_hash
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _password_reset_token_from_orm(row) if row else None

    async def mark_used(self, token_id: uuid.UUID) -> None:
        stmt = (
            update(models.PasswordResetToken)
            .where(models.PasswordResetToken.id == token_id)
            .values(used_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)


def _firewall_from_orm(row: models.Firewall) -> Firewall:
    return Firewall(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        pfsense_version=row.pfsense_version,
        status=row.status,
        last_seen_at=row.last_seen_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _agent_token_from_orm(row: models.AgentToken) -> AgentToken:
    return AgentToken(
        id=row.id,
        firewall_id=row.firewall_id,
        token_hash=row.token_hash,
        status=row.status,
        created_at=row.created_at,
        revoked_at=row.revoked_at,
    )


class SqlAlchemyFirewallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, firewall: Firewall) -> Firewall:
        row = models.Firewall(
            id=firewall.id,
            organization_id=firewall.organization_id,
            name=firewall.name,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _firewall_from_orm(row)

    async def get_by_id(self, firewall_id: uuid.UUID) -> Firewall | None:
        row = await self._session.get(models.Firewall, firewall_id)
        return _firewall_from_orm(row) if row else None

    async def list_active_for_org(
        self, organization_id: uuid.UUID, cursor: uuid.UUID | None, limit: int
    ) -> list[Firewall]:
        stmt = select(models.Firewall).where(
            models.Firewall.organization_id == organization_id,
            models.Firewall.deleted_at.is_(None),
        )
        if cursor is not None:
            stmt = stmt.where(models.Firewall.id > cursor)
        stmt = stmt.order_by(models.Firewall.id).limit(limit)
        result = await self._session.execute(stmt)
        return [_firewall_from_orm(row) for row in result.scalars().all()]

    async def update(self, firewall: Firewall) -> Firewall:
        row = await self._session.get(models.Firewall, firewall.id)
        if row is None:
            raise ValueError(f"Firewall {firewall.id} not found")
        row.name = firewall.name
        row.pfsense_version = firewall.pfsense_version
        row.status = firewall.status
        row.last_seen_at = firewall.last_seen_at
        row.deleted_at = firewall.deleted_at
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return _firewall_from_orm(row)

    async def record_check_in(self, firewall_id: uuid.UUID, pfsense_version: str | None) -> None:
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "status": "active",
            "last_seen_at": now,
            "updated_at": now,
        }
        if pfsense_version is not None:
            values["pfsense_version"] = pfsense_version
        stmt = update(models.Firewall).where(models.Firewall.id == firewall_id).values(**values)
        await self._session.execute(stmt)


class SqlAlchemyAgentTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, token: AgentToken) -> AgentToken:
        row = models.AgentToken(
            id=token.id,
            firewall_id=token.firewall_id,
            token_hash=token.token_hash,
            status=token.status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _agent_token_from_orm(row)

    async def get_active_for_firewall(self, firewall_id: uuid.UUID) -> AgentToken | None:
        stmt = select(models.AgentToken).where(
            models.AgentToken.firewall_id == firewall_id,
            models.AgentToken.status == "active",
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _agent_token_from_orm(row) if row else None

    async def revoke_all_for_firewall(self, firewall_id: uuid.UUID) -> None:
        stmt = (
            update(models.AgentToken)
            .where(
                models.AgentToken.firewall_id == firewall_id,
                models.AgentToken.status == "active",
            )
            .values(status="revoked", revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def get_by_token_hash(self, token_hash: str) -> AgentToken | None:
        stmt = select(models.AgentToken).where(models.AgentToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _agent_token_from_orm(row) if row else None


def _snapshot_from_orm(row: models.Snapshot) -> Snapshot:
    return Snapshot(
        id=row.id,
        firewall_id=row.firewall_id,
        raw_payload=row.raw_payload,
        processing_status=row.processing_status,
        received_at=row.received_at,
        processed_at=row.processed_at,
    )


class SqlAlchemySnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, snapshot: Snapshot) -> Snapshot:
        row = models.Snapshot(
            id=snapshot.id,
            firewall_id=snapshot.firewall_id,
            raw_payload=snapshot.raw_payload,
            processing_status=snapshot.processing_status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _snapshot_from_orm(row)

    async def list_queued(self, limit: int = 10) -> list[Snapshot]:
        stmt = (
            select(models.Snapshot)
            .where(models.Snapshot.processing_status == "queued")
            .order_by(models.Snapshot.received_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return [_snapshot_from_orm(row) for row in result.scalars().all()]

    async def update_status(self, snapshot_id: uuid.UUID, status: str) -> None:
        values: dict = {"processing_status": status}
        if status == "done":
            values["processed_at"] = datetime.now(UTC)
        stmt = update(models.Snapshot).where(models.Snapshot.id == snapshot_id).values(**values)
        await self._session.execute(stmt)

    async def get_latest_for_firewall(self, firewall_id: uuid.UUID) -> Snapshot | None:
        stmt = (
            select(models.Snapshot)
            .where(models.Snapshot.firewall_id == firewall_id)
            .order_by(models.Snapshot.received_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _snapshot_from_orm(row) if row else None

    async def get_previous_for_firewall(
        self, firewall_id: uuid.UUID, before_id: uuid.UUID
    ) -> Snapshot | None:
        stmt = (
            select(models.Snapshot)
            .where(
                models.Snapshot.firewall_id == firewall_id,
                models.Snapshot.id != before_id,
                models.Snapshot.processing_status == "done",
            )
            .order_by(models.Snapshot.received_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _snapshot_from_orm(row) if row else None


def _finding_from_orm(row: models.Finding) -> Finding:
    return Finding(
        id=row.id,
        firewall_id=row.firewall_id,
        snapshot_id=row.snapshot_id,
        check_type=row.check_type,
        severity=row.severity,
        details=row.details,
        status=row.status,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


class SqlAlchemyFindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, finding: Finding) -> Finding:
        row = models.Finding(
            id=finding.id,
            firewall_id=finding.firewall_id,
            snapshot_id=finding.snapshot_id,
            check_type=finding.check_type,
            severity=finding.severity,
            details=finding.details,
            status=finding.status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _finding_from_orm(row)

    async def get_open_by_check_type(
        self, firewall_id: uuid.UUID, check_type: str
    ) -> Finding | None:
        stmt = select(models.Finding).where(
            models.Finding.firewall_id == firewall_id,
            models.Finding.check_type == check_type,
            models.Finding.status == "open",
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _finding_from_orm(row) if row else None

    async def list_for_firewall(
        self,
        firewall_id: uuid.UUID,
        status: str | None,
        severity: str | None,
        check_type: str | None,
    ) -> list[Finding]:
        stmt = select(models.Finding).where(models.Finding.firewall_id == firewall_id)
        if status is not None:
            stmt = stmt.where(models.Finding.status == status)
        if severity is not None:
            stmt = stmt.where(models.Finding.severity == severity)
        if check_type is not None:
            stmt = stmt.where(models.Finding.check_type == check_type)
        stmt = stmt.order_by(models.Finding.created_at.desc())
        result = await self._session.execute(stmt)
        return [_finding_from_orm(row) for row in result.scalars().all()]

    async def count_open_grouped_by_severity(
        self, firewall_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, int]]:
        if not firewall_ids:
            return {}
        stmt = (
            select(
                models.Finding.firewall_id,
                models.Finding.severity,
                func.count().label("count"),
            )
            .where(
                models.Finding.firewall_id.in_(firewall_ids),
                models.Finding.status == "open",
            )
            .group_by(models.Finding.firewall_id, models.Finding.severity)
        )
        result = await self._session.execute(stmt)
        counts: dict[uuid.UUID, dict[str, int]] = {}
        for firewall_id, severity, count in result.all():
            counts.setdefault(firewall_id, {})[severity] = count
        return counts

    async def get_by_id(self, finding_id: uuid.UUID) -> Finding | None:
        row = await self._session.get(models.Finding, finding_id)
        return _finding_from_orm(row) if row else None

    async def update_status(self, finding_id: uuid.UUID, status: str) -> Finding:
        row = await self._session.get(models.Finding, finding_id)
        if row is None:
            raise ValueError(f"Finding {finding_id} not found")
        row.status = status
        if status == "resolved":
            row.resolved_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return _finding_from_orm(row)


def _subscription_from_orm(row: models.Subscription) -> Subscription:
    return Subscription(
        id=row.id,
        account_id=row.account_id,
        tier=row.tier,
        status=row.status,
        stripe_customer_id=row.stripe_customer_id,
        stripe_subscription_id=row.stripe_subscription_id,
        current_period_end=row.current_period_end,
    )


class SqlAlchemySubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, subscription: Subscription) -> Subscription:
        row = models.Subscription(
            id=subscription.id,
            account_id=subscription.account_id,
            tier=subscription.tier,
            status=subscription.status,
            stripe_customer_id=subscription.stripe_customer_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            current_period_end=subscription.current_period_end,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _subscription_from_orm(row)

    async def get_by_account_id(self, account_id: uuid.UUID) -> Subscription | None:
        stmt = select(models.Subscription).where(models.Subscription.account_id == account_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _subscription_from_orm(row) if row else None

    async def update_from_stripe_event(
        self,
        account_id: uuid.UUID,
        *,
        tier: str,
        status: str,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        current_period_end: datetime | None = None,
    ) -> Subscription:
        stmt = select(models.Subscription).where(models.Subscription.account_id == account_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Subscription for account {account_id} not found")
        row.tier = tier
        row.status = status
        if stripe_customer_id is not None:
            row.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            row.stripe_subscription_id = stripe_subscription_id
        if current_period_end is not None:
            row.current_period_end = current_period_end
        await self._session.flush()
        await self._session.refresh(row)
        return _subscription_from_orm(row)


class SqlAlchemyWebhookEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, event_id: str) -> bool:
        stmt = select(models.WebhookEvent.id).where(models.WebhookEvent.event_id == event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(self, event_id: str, event_type: str) -> WebhookEvent:
        row = models.WebhookEvent(event_id=event_id, event_type=event_type)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return WebhookEvent(
            id=row.id,
            event_id=row.event_id,
            event_type=row.event_type,
            processed_at=row.processed_at,
        )


def _alert_channel_from_orm(row: models.AlertChannel) -> AlertChannel:
    return AlertChannel(
        id=row.id,
        organization_id=row.organization_id,
        type=row.type,
        config=row.config,
        active=row.active,
    )


def _alert_rule_from_orm(row: models.AlertRule) -> AlertRule:
    return AlertRule(
        id=row.id,
        organization_id=row.organization_id,
        firewall_id=row.firewall_id,
        metric=row.metric,
        operator=row.operator,
        threshold=float(row.threshold),
        duration_minutes=row.duration_minutes,
        alert_channel_id=row.alert_channel_id,
        active=row.active,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _alert_delivery_from_orm(row: models.AlertDelivery) -> AlertDelivery:
    return AlertDelivery(
        id=row.id,
        finding_id=row.finding_id,
        alert_rule_id=row.alert_rule_id,
        alert_channel_id=row.alert_channel_id,
        status=row.status,
        sent_at=row.sent_at,
        error=row.error,
    )


class SqlAlchemyAlertChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, channel: AlertChannel) -> AlertChannel:
        row = models.AlertChannel(
            id=channel.id,
            organization_id=channel.organization_id,
            type=channel.type,
            config=channel.config,
            active=channel.active,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _alert_channel_from_orm(row)

    async def get_by_id(self, channel_id: uuid.UUID) -> AlertChannel | None:
        row = await self._session.get(models.AlertChannel, channel_id)
        return _alert_channel_from_orm(row) if row else None

    async def list_active_for_org(self, organization_id: uuid.UUID) -> list[AlertChannel]:
        stmt = select(models.AlertChannel).where(
            models.AlertChannel.organization_id == organization_id,
            models.AlertChannel.active.is_(True),
        )
        result = await self._session.execute(stmt)
        return [_alert_channel_from_orm(row) for row in result.scalars().all()]

    async def list_for_org(self, organization_id: uuid.UUID) -> list[AlertChannel]:
        stmt = select(models.AlertChannel).where(
            models.AlertChannel.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return [_alert_channel_from_orm(row) for row in result.scalars().all()]

    async def update(self, channel: AlertChannel) -> AlertChannel:
        row = await self._session.get(models.AlertChannel, channel.id)
        if row is None:
            raise ValueError(f"AlertChannel {channel.id} not found")
        row.type = channel.type
        row.config = channel.config
        row.active = channel.active
        await self._session.flush()
        await self._session.refresh(row)
        return _alert_channel_from_orm(row)

    async def delete(self, channel_id: uuid.UUID) -> None:
        row = await self._session.get(models.AlertChannel, channel_id)
        if row is not None:
            await self._session.delete(row)


class SqlAlchemyAlertRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, rule: AlertRule) -> AlertRule:
        row = models.AlertRule(
            id=rule.id,
            organization_id=rule.organization_id,
            firewall_id=rule.firewall_id,
            metric=rule.metric,
            operator=rule.operator,
            threshold=rule.threshold,
            duration_minutes=rule.duration_minutes,
            alert_channel_id=rule.alert_channel_id,
            active=rule.active,
            created_by_user_id=rule.created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _alert_rule_from_orm(row)

    async def get_by_id(self, rule_id: uuid.UUID) -> AlertRule | None:
        row = await self._session.get(models.AlertRule, rule_id)
        return _alert_rule_from_orm(row) if row else None

    async def list_for_org(self, organization_id: uuid.UUID) -> list[AlertRule]:
        stmt = select(models.AlertRule).where(
            models.AlertRule.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return [_alert_rule_from_orm(row) for row in result.scalars().all()]

    async def update(self, rule: AlertRule) -> AlertRule:
        row = await self._session.get(models.AlertRule, rule.id)
        if row is None:
            raise ValueError(f"AlertRule {rule.id} not found")
        row.metric = rule.metric
        row.operator = rule.operator
        row.threshold = rule.threshold
        row.duration_minutes = rule.duration_minutes
        row.alert_channel_id = rule.alert_channel_id
        row.active = rule.active
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return _alert_rule_from_orm(row)

    async def delete(self, rule_id: uuid.UUID) -> None:
        row = await self._session.get(models.AlertRule, rule_id)
        if row is not None:
            await self._session.delete(row)


class SqlAlchemyAlertDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, delivery: AlertDelivery) -> AlertDelivery:
        row = models.AlertDelivery(
            id=delivery.id,
            finding_id=delivery.finding_id,
            alert_rule_id=delivery.alert_rule_id,
            alert_channel_id=delivery.alert_channel_id,
            status=delivery.status,
            sent_at=delivery.sent_at,
            error=delivery.error,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _alert_delivery_from_orm(row)

    async def update_status(
        self, delivery_id: uuid.UUID, *, status: str, error: str | None = None
    ) -> AlertDelivery:
        row = await self._session.get(models.AlertDelivery, delivery_id)
        if row is None:
            raise ValueError(f"AlertDelivery {delivery_id} not found")
        row.status = status
        row.error = error
        if status == "sent":
            row.sent_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return _alert_delivery_from_orm(row)

    async def list_for_finding(self, finding_id: uuid.UUID) -> list[AlertDelivery]:
        stmt = select(models.AlertDelivery).where(
            models.AlertDelivery.finding_id == finding_id,
        )
        result = await self._session.execute(stmt)
        return [_alert_delivery_from_orm(row) for row in result.scalars().all()]


def _firewall_command_from_orm(row: models.FirewallCommand) -> FirewallCommand:
    return FirewallCommand(
        id=row.id,
        firewall_id=row.firewall_id,
        user_id=row.user_id,
        command_type=row.command_type,
        payload=row.payload,
        preview=row.preview,
        status=row.status,
        confirmed_at=row.confirmed_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
        applied_at=row.applied_at,
    )


def _remote_change_log_from_orm(row: models.RemoteChangeLog) -> RemoteChangeLog:
    return RemoteChangeLog(
        id=row.id,
        firewall_command_id=row.firewall_command_id,
        firewall_id=row.firewall_id,
        user_id=row.user_id,
        before_state=row.before_state,
        after_state=row.after_state,
        applied_at=row.applied_at,
        rolled_back_at=row.rolled_back_at,
        rolled_back_by_user_id=row.rolled_back_by_user_id,
        record_hash=row.record_hash,
    )


class SqlAlchemyFirewallCommandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, command: FirewallCommand) -> FirewallCommand:
        row = models.FirewallCommand(
            id=command.id,
            firewall_id=command.firewall_id,
            user_id=command.user_id,
            command_type=command.command_type,
            payload=command.payload,
            preview=command.preview,
            status=command.status,
            confirmed_at=command.confirmed_at,
            expires_at=command.expires_at,
            applied_at=command.applied_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _firewall_command_from_orm(row)

    async def get_by_id(self, command_id: uuid.UUID) -> FirewallCommand | None:
        row = await self._session.get(models.FirewallCommand, command_id)
        return _firewall_command_from_orm(row) if row else None

    async def update_status(
        self,
        command_id: uuid.UUID,
        *,
        status: str,
        confirmed_at: datetime | None = None,
        applied_at: datetime | None = None,
    ) -> FirewallCommand:
        row = await self._session.get(models.FirewallCommand, command_id)
        if row is None:
            raise ValueError(f"FirewallCommand {command_id} not found")
        row.status = status
        if confirmed_at is not None:
            row.confirmed_at = confirmed_at
        if applied_at is not None:
            row.applied_at = applied_at
        await self._session.flush()
        await self._session.refresh(row)
        return _firewall_command_from_orm(row)

    async def list_for_firewall(self, firewall_id: uuid.UUID) -> list[FirewallCommand]:
        stmt = (
            select(models.FirewallCommand)
            .where(models.FirewallCommand.firewall_id == firewall_id)
            .order_by(models.FirewallCommand.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_firewall_command_from_orm(row) for row in result.scalars().all()]

    async def list_sent_to_agent(self, firewall_id: uuid.UUID) -> list[FirewallCommand]:
        stmt = select(models.FirewallCommand).where(
            models.FirewallCommand.firewall_id == firewall_id,
            models.FirewallCommand.status == "sent_to_agent",
        )
        result = await self._session.execute(stmt)
        return [_firewall_command_from_orm(row) for row in result.scalars().all()]


class SqlAlchemyRemoteChangeLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: RemoteChangeLog) -> RemoteChangeLog:
        row = models.RemoteChangeLog(
            id=log.id,
            firewall_command_id=log.firewall_command_id,
            firewall_id=log.firewall_id,
            user_id=log.user_id,
            before_state=log.before_state,
            after_state=log.after_state,
            applied_at=log.applied_at,
            rolled_back_at=log.rolled_back_at,
            rolled_back_by_user_id=log.rolled_back_by_user_id,
            record_hash=log.record_hash,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _remote_change_log_from_orm(row)

    async def get_latest_for_firewall(self, firewall_id: uuid.UUID) -> RemoteChangeLog | None:
        stmt = (
            select(models.RemoteChangeLog)
            .where(models.RemoteChangeLog.firewall_id == firewall_id)
            .order_by(models.RemoteChangeLog.applied_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _remote_change_log_from_orm(row) if row else None

    async def list_for_firewall(self, firewall_id: uuid.UUID) -> list[RemoteChangeLog]:
        stmt = (
            select(models.RemoteChangeLog)
            .where(models.RemoteChangeLog.firewall_id == firewall_id)
            .order_by(models.RemoteChangeLog.applied_at.asc())
        )
        result = await self._session.execute(stmt)
        return [_remote_change_log_from_orm(row) for row in result.scalars().all()]

    async def mark_rolled_back(
        self,
        log_id: uuid.UUID,
        *,
        rolled_back_by_user_id: uuid.UUID,
        rolled_back_at: datetime,
    ) -> RemoteChangeLog:
        row = await self._session.get(models.RemoteChangeLog, log_id)
        if row is None:
            raise ValueError(f"RemoteChangeLog {log_id} not found")
        row.rolled_back_at = rolled_back_at
        row.rolled_back_by_user_id = rolled_back_by_user_id
        await self._session.flush()
        await self._session.refresh(row)
        return _remote_change_log_from_orm(row)


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
