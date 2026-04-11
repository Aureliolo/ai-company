"""Unit tests for secret backend stubs."""

import pytest

from synthorg.integrations.config import SecretBackendConfig
from synthorg.integrations.connections.secret_backends.factory import (
    create_secret_backend,
)


@pytest.mark.unit
class TestSecretBackendStubs:
    @pytest.mark.parametrize(
        "backend_type",
        [
            "secret_manager_vault",
            "secret_manager_cloud_a",
            "secret_manager_cloud_b",
        ],
    )
    def test_stub_raises_not_implemented(
        self,
        backend_type: str,
    ) -> None:
        config = SecretBackendConfig(backend_type=backend_type)  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            create_secret_backend(config, db_path="/tmp/test.db")  # noqa: S108
