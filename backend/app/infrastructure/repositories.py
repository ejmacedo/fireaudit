import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Account, Organization, RefreshToken, User
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


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
