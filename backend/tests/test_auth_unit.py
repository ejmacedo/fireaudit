"""Phase 3 pure unit tests: use cases with in-memory fakes, no DB, no FastAPI."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.protocols import AccessTokenClaims
from app.application.use_cases.login_user import LoginRequest, LoginUser
from app.application.use_cases.logout_user import LogoutRequest, LogoutUser
from app.application.use_cases.refresh_session import RefreshRequest, RefreshSession
from app.domain.entities import RefreshToken, User
from app.domain.errors import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
)


class FakeUserRepo:
    def __init__(self) -> None:
        self._by_email: dict[str, User] = {}
        self._by_id: dict[uuid.UUID, User] = {}

    def seed(self, user: User) -> None:
        self._by_email[user.email] = user
        self._by_id[user.id] = user

    async def get_by_email(self, email: str) -> User | None:
        return self._by_email.get(email)

    async def get_by_id(self, user_id: uuid.UUID):
        return self._by_id.get(user_id)


class FakeRefreshRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, RefreshToken] = {}

    async def create(self, token: RefreshToken) -> RefreshToken:
        self._items[token.id] = token
        return token

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        for t in self._items.values():
            if t.token_hash == token_hash:
                return t
        return None

    async def revoke(self, token_id: uuid.UUID) -> None:
        current = self._items[token_id]
        self._items[token_id] = RefreshToken(
            id=current.id,
            user_id=current.user_id,
            token_hash=current.token_hash,
            expires_at=current.expires_at,
            revoked_at=datetime.now(UTC),
            created_at=current.created_at,
        )


class FakeVerifier:
    def __init__(self, expected: str) -> None:
        self._expected = expected

    def verify(self, plain: str, hashed: str) -> bool:
        return plain == self._expected


class FakeTokens:
    def create_access_token(self, user_id, account_id) -> str:
        return f"access:{user_id}"

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        raise NotImplementedError

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(16)

    def hash_refresh_token(self, plain: str) -> str:
        return hashlib.sha256(plain.encode()).hexdigest()


class FakeUoW:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None: ...


def _make_user(email: str = "u@e.co") -> User:
    return User(
        account_id=uuid.uuid4(),
        email=email,
        password_hash="$argon2id$dummy",
    )


async def test_login_wrong_password_raises_invalid_credentials():
    users = FakeUserRepo()
    user = _make_user()
    users.seed(user)
    use_case = LoginUser(
        users=users,
        refresh_tokens=FakeRefreshRepo(),
        verifier=FakeVerifier(expected="correct"),
        tokens=FakeTokens(),
        uow=FakeUoW(),
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
    )
    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(LoginRequest(email=user.email, password="wrong"))


async def test_login_unknown_email_raises_invalid_credentials():
    use_case = LoginUser(
        users=FakeUserRepo(),
        refresh_tokens=FakeRefreshRepo(),
        verifier=FakeVerifier(expected="anything"),
        tokens=FakeTokens(),
        uow=FakeUoW(),
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
    )
    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(LoginRequest(email="nope@e.co", password="anything"))


async def test_refresh_rotation_invalidates_previous():
    users = FakeUserRepo()
    refresh_repo = FakeRefreshRepo()
    user = _make_user()
    users.seed(user)
    tokens = FakeTokens()

    login = LoginUser(
        users=users,
        refresh_tokens=refresh_repo,
        verifier=FakeVerifier(expected="pw"),
        tokens=tokens,
        uow=FakeUoW(),
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
    )
    result = await login.execute(LoginRequest(email=user.email, password="pw"))

    refresh_uc = RefreshSession(
        users=users,
        refresh_tokens=refresh_repo,
        tokens=tokens,
        uow=FakeUoW(),
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
    )
    new = await refresh_uc.execute(RefreshRequest(refresh_token=result.refresh_token))
    assert new.refresh_token != result.refresh_token

    with pytest.raises(RefreshTokenRevokedError):
        await refresh_uc.execute(RefreshRequest(refresh_token=result.refresh_token))


async def test_refresh_expired_raises():
    users = FakeUserRepo()
    refresh_repo = FakeRefreshRepo()
    user = _make_user()
    users.seed(user)
    tokens = FakeTokens()
    plain = tokens.generate_refresh_token()
    await refresh_repo.create(
        RefreshToken(
            user_id=user.id,
            token_hash=tokens.hash_refresh_token(plain),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    use_case = RefreshSession(
        users=users,
        refresh_tokens=refresh_repo,
        tokens=tokens,
        uow=FakeUoW(),
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
    )
    with pytest.raises(RefreshTokenExpiredError):
        await use_case.execute(RefreshRequest(refresh_token=plain))


async def test_refresh_unknown_raises():
    use_case = RefreshSession(
        users=FakeUserRepo(),
        refresh_tokens=FakeRefreshRepo(),
        tokens=FakeTokens(),
        uow=FakeUoW(),
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
    )
    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(RefreshRequest(refresh_token="does-not-exist"))


async def test_logout_revokes_token_idempotently():
    refresh_repo = FakeRefreshRepo()
    tokens = FakeTokens()
    plain = tokens.generate_refresh_token()
    stored = await refresh_repo.create(
        RefreshToken(
            user_id=uuid.uuid4(),
            token_hash=tokens.hash_refresh_token(plain),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    uow = FakeUoW()
    use_case = LogoutUser(refresh_tokens=refresh_repo, tokens=tokens, uow=uow)

    await use_case.execute(LogoutRequest(refresh_token=plain))
    assert refresh_repo._items[stored.id].revoked_at is not None
    assert uow.commits == 1

    # Second logout is a no-op.
    await use_case.execute(LogoutRequest(refresh_token=plain))
    assert uow.commits == 1
