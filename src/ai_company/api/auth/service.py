"""Authentication service — password hashing, JWT ops, API key hashing."""

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import argon2
import jwt

from ai_company.api.auth.models import User  # noqa: TC001
from ai_company.observability import get_logger
from ai_company.observability.events.api import API_AUTH_FAILED

if TYPE_CHECKING:
    from ai_company.api.auth.config import AuthConfig

logger = get_logger(__name__)

_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class AuthService:
    """Immutable authentication operations.

    Args:
        config: Authentication configuration (carries JWT secret).
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    def hash_password(self, password: str) -> str:
        """Hash a password with Argon2id.

        Args:
            password: Plaintext password.

        Returns:
            Argon2id hash string.
        """
        return _hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against an Argon2id hash.

        Args:
            password: Plaintext password to check.
            password_hash: Stored Argon2id hash.

        Returns:
            ``True`` if the password matches.
        """
        try:
            return _hasher.verify(password_hash, password)
        except argon2.exceptions.VerifyMismatchError:
            return False
        except argon2.exceptions.VerificationError:
            logger.warning(
                API_AUTH_FAILED,
                reason="hash_verification_error",
                exc_info=True,
            )
            return False
        except argon2.exceptions.InvalidHashError:
            logger.error(
                API_AUTH_FAILED,
                reason="invalid_hash_data_corruption",
                exc_info=True,
            )
            return False

    async def hash_password_async(self, password: str) -> str:
        """Hash a password with Argon2id in a thread executor.

        Offloads the CPU-intensive hashing to avoid blocking the
        event loop.

        Args:
            password: Plaintext password.

        Returns:
            Argon2id hash string.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.hash_password, password)

    async def verify_password_async(
        self,
        password: str,
        password_hash: str,
    ) -> bool:
        """Verify a password against an Argon2id hash in a thread executor.

        Offloads the CPU-intensive verification to avoid blocking the
        event loop.

        Args:
            password: Plaintext password to check.
            password_hash: Stored Argon2id hash.

        Returns:
            ``True`` if the password matches.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.verify_password, password, password_hash
        )

    def create_token(self, user: User) -> tuple[str, int]:
        """Create a JWT for the given user.

        Args:
            user: Authenticated user.

        Returns:
            Tuple of (encoded JWT string, expiry seconds).

        Raises:
            RuntimeError: If the JWT secret is empty.
        """
        if not self._config.jwt_secret:
            msg = "JWT secret not configured"
            raise RuntimeError(msg)
        now = datetime.now(UTC)
        expiry_seconds = self._config.jwt_expiry_minutes * 60
        pwd_sig = hashlib.sha256(
            user.password_hash.encode(),
        ).hexdigest()[:16]
        payload: dict[str, Any] = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
            "must_change_password": user.must_change_password,
            "pwd_sig": pwd_sig,
            "iat": now,
            "exp": now + timedelta(seconds=expiry_seconds),
        }
        token = jwt.encode(
            payload,
            self._config.jwt_secret,
            algorithm=self._config.jwt_algorithm,
        )
        return token, expiry_seconds

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT.

        Args:
            token: Encoded JWT string.

        Returns:
            Decoded claims dictionary.

        Raises:
            RuntimeError: If the JWT secret is empty.
            jwt.InvalidTokenError: If the token is invalid or expired.
        """
        if not self._config.jwt_secret:
            msg = "JWT secret not configured"
            raise RuntimeError(msg)
        return jwt.decode(
            token,
            self._config.jwt_secret,
            algorithms=[self._config.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        """Compute SHA-256 hex digest of a raw API key.

        Args:
            raw_key: The plaintext API key.

        Returns:
            Lowercase hex digest.
        """
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @staticmethod
    def generate_api_key() -> str:
        """Generate a cryptographically secure API key.

        Returns:
            URL-safe base64 string (43 chars).
        """
        return secrets.token_urlsafe(32)
