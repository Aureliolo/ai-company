"""Cloud secret manager backend -- variant B (stub).

Full implementation deferred -- this stub satisfies the
pluggable-backend protocol and raises ``NotImplementedError``
on all operations.
"""

from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    SECRET_BACKEND_UNAVAILABLE,
)

logger = get_logger(__name__)

_BACKEND_NAME = "secret_manager_cloud_b"
_MSG = "Cloud secret manager (variant B) backend not yet implemented"


class AzureKeyVaultBackend:
    """Stub for Azure Key Vault secret storage."""

    @property
    def backend_name(self) -> str:
        """Return backend identifier."""
        return _BACKEND_NAME

    async def store(self, secret_id: str, value: bytes) -> None:  # noqa: ARG002
        """Not implemented."""
        logger.warning(
            SECRET_BACKEND_UNAVAILABLE,
            backend=_BACKEND_NAME,
            operation="store",
            secret_id=secret_id,
        )
        raise NotImplementedError(_MSG)

    async def retrieve(self, secret_id: str) -> bytes | None:
        """Not implemented."""
        logger.warning(
            SECRET_BACKEND_UNAVAILABLE,
            backend=_BACKEND_NAME,
            operation="retrieve",
            secret_id=secret_id,
        )
        raise NotImplementedError(_MSG)

    async def delete(self, secret_id: str) -> bool:
        """Not implemented."""
        logger.warning(
            SECRET_BACKEND_UNAVAILABLE,
            backend=_BACKEND_NAME,
            operation="delete",
            secret_id=secret_id,
        )
        raise NotImplementedError(_MSG)

    async def rotate(self, old_id: str, new_value: bytes) -> str:  # noqa: ARG002
        """Not implemented."""
        logger.warning(
            SECRET_BACKEND_UNAVAILABLE,
            backend=_BACKEND_NAME,
            operation="rotate",
            old_id=old_id,
        )
        raise NotImplementedError(_MSG)

    async def close(self) -> None:
        """No resources to release."""
        return
