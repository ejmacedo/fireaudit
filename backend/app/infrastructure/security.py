import hashlib
import hmac as _hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.application.protocols import AccessTokenClaims
from app.core.config import settings
from app.domain.errors import InvalidRefreshTokenError

_hasher = Argon2Hasher()
_JWT_ALGORITHM = "HS256"


class Argon2PasswordHasher:
    """Adapter for argon2-cffi implementing app.application.protocols.PasswordHasher."""

    def hash(self, plain: str) -> str:
        return _hasher.hash(plain)


class Argon2PasswordVerifier:
    """Adapter implementing app.application.protocols.PasswordVerifier."""

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return _hasher.verify(hashed, plain)
        except VerifyMismatchError:
            return False
        except Exception:
            return False


class JoseTokenService:
    """JWT (access) + opaque refresh token implementation."""

    def __init__(self, secret: str, access_token_ttl_minutes: int) -> None:
        self._secret = secret
        self._access_ttl_min = access_token_ttl_minutes

    def create_access_token(self, user_id: uuid.UUID, account_id: uuid.UUID) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "account_id": str(account_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._access_ttl_min)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=_JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_JWT_ALGORITHM])
            return AccessTokenClaims(
                user_id=uuid.UUID(payload["sub"]),
                account_id=uuid.UUID(payload["account_id"]),
            )
        except (JWTError, KeyError, ValueError) as exc:
            raise InvalidRefreshTokenError() from exc

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(32)

    def hash_refresh_token(self, plain: str) -> str:
        return hashlib.sha256(plain.encode("utf-8")).hexdigest()


class HMACVerifier:
    """HMAC-SHA256 signature verifier for snapshot ingest endpoint."""

    @staticmethod
    def compute(key: str, body: bytes) -> str:
        return _hmac.new(key.encode(), body, hashlib.sha256).hexdigest()

    @staticmethod
    def verify(key: str, body: bytes, signature: str) -> bool:
        expected = HMACVerifier.compute(key, body)
        return _hmac.compare_digest(expected, signature)


def build_token_service() -> JoseTokenService:
    return JoseTokenService(
        secret=settings.jwt_secret,
        access_token_ttl_minutes=settings.jwt_access_token_expire_minutes,
    )
