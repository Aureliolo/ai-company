"""Unit tests for the secret backend factory.

Covers the routing contract (which config discriminator produces
which backend) plus the two failure modes added alongside the
``encrypted_postgres`` adapter: missing ``db_path`` for
``encrypted_sqlite`` and missing ``pg_pool`` for
``encrypted_postgres``.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from synthorg.integrations.config import SecretBackendConfig
from synthorg.integrations.connections.secret_backends.encrypted_postgres import (
    EncryptedPostgresSecretBackend,
)
from synthorg.integrations.connections.secret_backends.encrypted_sqlite import (
    EncryptedSqliteSecretBackend,
)
from synthorg.integrations.connections.secret_backends.env_var import (
    EnvVarSecretBackend,
)
from synthorg.integrations.connections.secret_backends.factory import (
    create_secret_backend,
)


@pytest.mark.unit
class TestFactoryRouting:
    def test_encrypted_sqlite_requires_db_path(self) -> None:
        config = SecretBackendConfig(backend_type="encrypted_sqlite")
        with pytest.raises(
            ValueError, match="db_path is required for encrypted_sqlite"
        ):
            create_secret_backend(config)

    def test_encrypted_postgres_requires_pg_pool(self) -> None:
        config = SecretBackendConfig(backend_type="encrypted_postgres")
        with pytest.raises(
            ValueError, match="pg_pool is required for encrypted_postgres"
        ):
            create_secret_backend(config)

    def test_env_var_needs_no_storage(self) -> None:
        config = SecretBackendConfig(backend_type="env_var")
        backend = create_secret_backend(config)
        assert isinstance(backend, EnvVarSecretBackend)
        assert backend.backend_name == "env_var"

    def test_encrypted_sqlite_constructed_when_key_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # A valid Fernet key (44-char url-safe base64 of 32 zero bytes).
        from cryptography.fernet import Fernet

        monkeypatch.setenv("SYNTHORG_MASTER_KEY", Fernet.generate_key().decode())
        config = SecretBackendConfig(backend_type="encrypted_sqlite")
        db_path = str(tmp_path / "secrets.db")
        backend = create_secret_backend(config, db_path=db_path)
        assert isinstance(backend, EncryptedSqliteSecretBackend)
        assert backend.backend_name == "encrypted_sqlite"

    def test_encrypted_postgres_constructed_when_key_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from cryptography.fernet import Fernet

        monkeypatch.setenv("SYNTHORG_MASTER_KEY", Fernet.generate_key().decode())
        config = SecretBackendConfig(backend_type="encrypted_postgres")
        pool = MagicMock()
        backend = create_secret_backend(config, pg_pool=pool)
        assert isinstance(backend, EncryptedPostgresSecretBackend)
        assert backend.backend_name == "encrypted_postgres"

    @pytest.mark.parametrize(
        "backend_type",
        [
            "secret_manager_vault",
            "secret_manager_cloud_a",
            "secret_manager_cloud_b",
        ],
    )
    def test_stub_backends_not_implemented(self, backend_type: str) -> None:
        config = SecretBackendConfig(backend_type=backend_type)  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            create_secret_backend(config)


@pytest.mark.unit
class TestEncryptedPostgresKeyLoading:
    def test_missing_master_key_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from synthorg.integrations.errors import MasterKeyError

        monkeypatch.delenv("SYNTHORG_MASTER_KEY", raising=False)
        pool = MagicMock()
        with pytest.raises(MasterKeyError, match="SYNTHORG_MASTER_KEY is not set"):
            EncryptedPostgresSecretBackend(pool=pool)

    def test_invalid_master_key_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from synthorg.integrations.errors import MasterKeyError

        monkeypatch.setenv("SYNTHORG_MASTER_KEY", "not-a-valid-fernet-key")
        pool = MagicMock()
        with pytest.raises(MasterKeyError, match="Invalid Fernet key"):
            EncryptedPostgresSecretBackend(pool=pool)
