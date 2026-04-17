"""Secret backend factory.

Creates a ``SecretBackend`` instance from configuration.
"""

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from synthorg.integrations.config import SecretBackendConfig  # noqa: TC001
from synthorg.integrations.connections.secret_backends.encrypted_postgres import (
    EncryptedPostgresSecretBackend,
)
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

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = get_logger(__name__)


@dataclass(frozen=True)
class SecretBackendSelection:
    """Result of :func:`resolve_secret_backend_config`.

    Attributes:
        config: The (possibly rewritten) ``SecretBackendConfig`` with
            the resolved ``backend_type``.
        reason: Human-readable explanation of any auto-selection or
            downgrade that happened, or empty string if the config
            was honoured as-is.
        level: Log level appropriate for ``reason`` -- ``"info"`` for
            silent honour-as-is, ``"warning"`` for a benign promotion
            (sqlite -> postgres in postgres mode), ``"error"`` for a
            security-relevant downgrade (missing master key, missing
            store). Callers log the reason at this level.
    """

    config: SecretBackendConfig
    reason: str
    level: str


def resolve_secret_backend_config(
    config: SecretBackendConfig,
    *,
    postgres_mode: bool,
    pg_pool_available: bool,
    sqlite_db_path: str | None,
) -> SecretBackendSelection:
    """Auto-select the correct secret backend for the active persistence.

    Selection rules (checked top to bottom):

    1. Default ``encrypted_sqlite`` + postgres mode + live pool
       -> promote to ``encrypted_postgres`` (benign, WARNING).
    2. Default ``encrypted_sqlite`` + postgres mode + no pool ->
       downgrade to ``env_var`` (ERROR: integrations degraded).
    3. ``encrypted_sqlite`` with no db_path (sqlite mode without
       SYNTHORG_DB_PATH) -> downgrade to ``env_var`` (ERROR).
    4. Explicit ``encrypted_postgres`` without a live pool ->
       downgrade to ``env_var`` (ERROR).
    5. Any ``encrypted_*`` with no ``SYNTHORG_MASTER_KEY`` env var ->
       downgrade to ``env_var`` (ERROR: no at-rest encryption).
    6. Otherwise honour the config as-is.

    Args:
        config: Configured secret backend.
        postgres_mode: Whether the active persistence backend is
            Postgres (vs SQLite).
        pg_pool_available: Whether ``persistence.get_db()`` yielded a
            usable pool. Set to ``False`` when the persistence layer
            failed to connect.
        sqlite_db_path: SQLite DB path if available, else ``None``.

    Returns:
        A :class:`SecretBackendSelection` describing the resolved
        config plus a human-readable reason (empty if unchanged).
    """
    resolved = config.backend_type

    if resolved == "encrypted_sqlite" and postgres_mode:
        if pg_pool_available:
            resolved = "encrypted_postgres"
            reason = (
                "default encrypted_sqlite promoted to encrypted_postgres "
                "to match Postgres persistence"
            )
            level = "warning"
        else:
            resolved = "env_var"
            reason = (
                "encrypted secret backend requested in postgres mode but "
                "no pool is available; falling back to env_var"
            )
            level = "error"
    elif resolved == "encrypted_sqlite" and sqlite_db_path is None:
        resolved = "env_var"
        reason = (
            "encrypted_sqlite secret backend has no db_path; falling back to env_var"
        )
        level = "error"
    elif resolved == "encrypted_postgres" and not pg_pool_available:
        resolved = "env_var"
        reason = (
            "encrypted_postgres secret backend has no pg_pool; falling back to env_var"
        )
        level = "error"
    else:
        reason = ""
        level = "info"

    # Master key check applies after the first pass; even an
    # explicitly-configured encrypted backend still needs the key.
    if resolved in ("encrypted_sqlite", "encrypted_postgres"):
        master_key_env = (
            config.encrypted_sqlite.master_key_env
            if resolved == "encrypted_sqlite"
            else config.encrypted_postgres.master_key_env
        )
        if not os.environ.get(master_key_env, "").strip():
            resolved = "env_var"
            reason = (
                f"{master_key_env} is not set; encrypted secret backend "
                "requires a Fernet key. Falling back to env_var (no "
                f"at-rest encryption). Set {master_key_env} (URL-safe "
                "base64 of 32 bytes) to enable encrypted secret storage."
            )
            level = "error"

    if resolved != config.backend_type:
        config = config.model_copy(update={"backend_type": resolved})
    return SecretBackendSelection(config=config, reason=reason, level=level)


def create_secret_backend(
    config: SecretBackendConfig,
    *,
    db_path: str | None = None,
    pg_pool: "AsyncConnectionPool | None" = None,  # noqa: UP037
) -> SecretBackend:
    """Create a secret backend from configuration.

    Args:
        config: Secret backend configuration.
        db_path: SQLite database path (required for
            ``encrypted_sqlite``).
        pg_pool: Async Postgres connection pool (required for
            ``encrypted_postgres``).

    Returns:
        A configured ``SecretBackend`` instance.

    Raises:
        ValueError: If the backend type is unknown or misconfigured.
        NotImplementedError: If the backend type is a stub.
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

    if backend_type == "encrypted_postgres":
        if pg_pool is None:
            logger.error(
                SECRET_BACKEND_UNAVAILABLE,
                backend=backend_type,
                error="pg_pool is required for encrypted_postgres",
            )
            msg = "pg_pool is required for encrypted_postgres secret backend"
            raise ValueError(msg)
        return EncryptedPostgresSecretBackend(
            pool=pg_pool,
            config=config.encrypted_postgres,
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
