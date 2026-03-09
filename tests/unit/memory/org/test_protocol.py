"""Tests for OrgMemoryBackend protocol compliance."""

from unittest.mock import AsyncMock

import pytest

from ai_company.memory.org.access_control import WriteAccessConfig
from ai_company.memory.org.hybrid_backend import HybridPromptRetrievalBackend
from ai_company.memory.org.protocol import OrgMemoryBackend

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestOrgMemoryBackendProtocol:
    """OrgMemoryBackend is runtime_checkable."""

    def test_hybrid_backend_is_instance(self) -> None:
        store = AsyncMock()
        backend = HybridPromptRetrievalBackend(
            core_policies=(),
            store=store,
            access_config=WriteAccessConfig(),
        )
        assert isinstance(backend, OrgMemoryBackend)
