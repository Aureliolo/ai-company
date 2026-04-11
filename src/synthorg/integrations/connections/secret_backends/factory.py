"""Secret backend factory.

Creates a ``SecretBackend`` instance from configuration.
"""

from synthorg.integrations.config import SecretBackendConfig  # noqa: TC001
from synthorg.integrations.connections.secret_backends.encrypted_sqlite import (
    EncryptedSqliteSecretBackend,
)
from synthorg.integrations.connections.secret_backends.env_var import (
    EnvVarSecretBackend,
)
from synthorg.integrations.connections.secret_backends.protocol import (
    SecretBackend,  # noqa: TC001
)
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    SECRET_BACKEND_UNAVAILABLE,
)

logger = get_logger(__name__)


def create_secret_backend(
    config: SecretBackendConfig,
    *,
    db_path: str | None = None,
) -> SecretBackend:
    """Create a secret backend from configuration.

    Args:
        config: Secret backend configuration.
        db_path: SQLite database path (required for encrypted_sqlite).

    Returns:
        A configured ``SecretBackend`` instance.

    Raises:
        ValueError: If the backend type is unknown or misconfigured.
    """
    backend_type = config.backend_type

    if backend_type == "encrypted_sqlite":
        if db_path is None:
            logger.error(
                SECRET_BACKEND_UNAVAILABLE,
                backend=backend_type,
                error="db_path is required for encrypted_sqlite",
            )
            msg = "db_path is required for encrypted_sqlite secret backend"
            raise ValueError(msg)
        return EncryptedSqliteSecretBackend(
            db_path=db_path,
            config=config.encrypted_sqlite,
        )

    if backend_type == "env_var":
        return EnvVarSecretBackend(config=config.env_var)

    stub_backends = {
        "secret_manager_vault",
        "secret_manager_cloud_a",
        "secret_manager_cloud_b",
    }
    if backend_type in stub_backends:
        logger.error(
            SECRET_BACKEND_UNAVAILABLE,
            backend=backend_type,
            error="backend type not yet implemented",
        )
        msg = f"{backend_type} secret backend not yet implemented"
        raise NotImplementedError(msg)

    logger.error(
        SECRET_BACKEND_UNAVAILABLE,
        backend=backend_type,
        error="unknown backend type",
    )
    msg = f"Unknown secret backend type: {backend_type}"
    raise ValueError(msg)
