from argon2 import PasswordHasher as Argon2Hasher

_hasher = Argon2Hasher()


class Argon2PasswordHasher:
    """Adapter for argon2-cffi implementing app.application.protocols.PasswordHasher."""

    def hash(self, plain: str) -> str:
        return _hasher.hash(plain)
