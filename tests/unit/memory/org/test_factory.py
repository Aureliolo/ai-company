"""Tests for org memory backend factory."""

from unittest.mock import MagicMock

import pytest

from synthorg.memory.org.config import OrgMemoryConfig
from synthorg.memory.org.errors import OrgMemoryConfigError
from synthorg.memory.org.factory import create_org_memory_backend
from synthorg.memory.org.hybrid_backend import HybridPromptRetrievalBackend
from synthorg.memory.org.store import OrgFactStore


def SQLiteOrgFactStore(_path: str) -> OrgFactStore:  # noqa: N802 - legacy name shim
    """Return a lightweight OrgFactStore mock for factory tests.

    After A4 consolidation, the real store comes from the persistence
    backend; factory unit tests only need *something* implementing the
    protocol to verify dispatch.
    """
    return MagicMock(spec=OrgFactStore)


@pytest.mark.unit
class TestCreateOrgMemoryBackend:
    """Factory dispatch tests."""

    def test_creates_hybrid_backend(self) -> None:
        config = OrgMemoryConfig()
        store = SQLiteOrgFactStore(":memory:")
        backend = create_org_memory_backend(config, store)
        assert isinstance(backend, HybridPromptRetrievalBackend)

    def test_creates_hybrid_with_policies(self) -> None:
        config = OrgMemoryConfig(
            core_policies=("Policy A", "Policy B"),
        )
        store = SQLiteOrgFactStore(":memory:")
        backend = create_org_memory_backend(config, store)
        assert isinstance(backend, HybridPromptRetrievalBackend)

    def test_unknown_backend_raises_config_error(self) -> None:
        config = OrgMemoryConfig.model_construct(
            backend="nonexistent_backend",
            core_policies=(),
            extended_store=OrgMemoryConfig().extended_store,
            write_access=OrgMemoryConfig().write_access,
        )
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConfigError, match="Unknown org memory backend"):
            create_org_memory_backend(config, store)
