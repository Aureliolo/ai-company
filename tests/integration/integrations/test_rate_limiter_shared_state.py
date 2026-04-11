"""Rate limiter shared state: verify coordinator structure."""

import pytest

from synthorg.integrations.rate_limiting.shared_state import (
    SharedRateLimitCoordinator,
    get_coordinator,
    set_coordinator_factory,
)


@pytest.mark.integration
class TestSharedRateLimitCoordinator:
    async def test_coordinator_acquire_rejects_over_budget(
        self,
        memory_bus: object,
    ) -> None:
        coord = SharedRateLimitCoordinator(
            bus=memory_bus,  # type: ignore[arg-type]
            connection_name="test-conn",
            max_rpm=2,
        )
        await coord.start()
        try:
            await coord.acquire()
            await coord.acquire()
            from synthorg.integrations.errors import (
                ConnectionRateLimitError,
            )

            with pytest.raises(ConnectionRateLimitError):
                await coord.acquire()
        finally:
            await coord.stop()


@pytest.mark.integration
class TestCoordinatorFactory:
    def test_factory_none_by_default(self) -> None:
        assert get_coordinator("nonexistent") is None

    def test_factory_creates_coordinator(self) -> None:
        from unittest.mock import MagicMock

        bus = MagicMock()
        set_coordinator_factory(
            lambda name: SharedRateLimitCoordinator(
                bus=bus,
                connection_name=name,
            ),
        )
        coord = get_coordinator("test")
        assert coord is not None
        assert coord._connection_name == "test"
