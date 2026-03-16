"""Fernet encryption for sensitive settings.

Values marked ``sensitive=True`` in the settings registry are encrypted
at rest using Fernet symmetric encryption.  The encryption key is read
from the ``SYNTHORG_SETTINGS_KEY`` environment variable.
"""

import os

from cryptography.fernet import Fernet, InvalidToken

from synthorg.observability import get_logger
from synthorg.observability.events.settings import SETTINGS_ENCRYPTION_ERROR
from synthorg.settings.errors import SettingsEncryptionError

logger = get_logger(__name__)

_ENV_VAR = "SYNTHORG_SETTINGS_KEY"


class SettingsEncryptor:
    """Fernet encrypt/decrypt wrapper for sensitive setting values.

    Args:
        key: A valid Fernet key (URL-safe base64-encoded 32-byte key).
    """

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Args:
            plaintext: The value to encrypt.

        Returns:
            Base64-encoded ciphertext string.

        Raises:
            SettingsEncryptionError: If encryption fails.
        """
        try:
            return self._fernet.encrypt(
                plaintext.encode("utf-8"),
            ).decode("ascii")
        except Exception as exc:
            logger.exception(
                SETTINGS_ENCRYPTION_ERROR,
                operation="encrypt",
                error=str(exc),
            )
            msg = "Failed to encrypt setting value"
            raise SettingsEncryptionError(msg) from exc

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string.

        Args:
            ciphertext: Base64-encoded ciphertext to decrypt.

        Returns:
            The decrypted plaintext string.

        Raises:
            SettingsEncryptionError: If decryption fails (wrong key,
                corrupted data, etc.).
        """
        try:
            return self._fernet.decrypt(
                ciphertext.encode("ascii"),
            ).decode("utf-8")
        except InvalidToken as exc:
            logger.exception(
                SETTINGS_ENCRYPTION_ERROR,
                operation="decrypt",
                error="invalid token or wrong key",
            )
            msg = "Failed to decrypt setting value — wrong key or corrupted data"
            raise SettingsEncryptionError(msg) from exc
        except Exception as exc:
            logger.exception(
                SETTINGS_ENCRYPTION_ERROR,
                operation="decrypt",
                error=str(exc),
            )
            msg = "Failed to decrypt setting value"
            raise SettingsEncryptionError(msg) from exc

    @classmethod
    def from_env(cls) -> SettingsEncryptor | None:
        """Create an encryptor from the ``SYNTHORG_SETTINGS_KEY`` env var.

        Returns:
            An encryptor instance, or ``None`` if the env var is not set.

        Raises:
            SettingsEncryptionError: If the env var is set but the key
                is invalid.
        """
        raw_or_none = os.environ.get(_ENV_VAR)
        if raw_or_none is None:
            return None
        raw = raw_or_none.strip()
        if not raw:
            msg = (
                f"{_ENV_VAR} is set but empty — "
                f"provide a valid Fernet key or unset the variable"
            )
            logger.exception(
                SETTINGS_ENCRYPTION_ERROR,
                operation="from_env",
                error=msg,
            )
            raise SettingsEncryptionError(msg)
        try:
            return cls(raw.encode("ascii"))
        except Exception as exc:
            logger.exception(
                SETTINGS_ENCRYPTION_ERROR,
                operation="from_env",
                error=str(exc),
            )
            msg = f"Invalid Fernet key in {_ENV_VAR}"
            raise SettingsEncryptionError(msg) from exc
