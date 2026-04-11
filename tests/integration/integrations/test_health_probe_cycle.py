"""Health prober integration: verify probe loop structure."""

import pytest

from synthorg.integrations.health.prober import (
    _CHECK_REGISTRY,
    HealthProberService,
)


@pytest.mark.integration
class TestHealthProberStructure:
    def test_check_registry_has_five_entries(self) -> None:
        assert len(_CHECK_REGISTRY) == 5

    def test_prober_constructs_with_defaults(self) -> None:
        from unittest.mock import AsyncMock

        catalog = AsyncMock()
        prober = HealthProberService(catalog=catalog)
        assert prober._interval == 300
        assert prober._unhealthy_threshold == 3
