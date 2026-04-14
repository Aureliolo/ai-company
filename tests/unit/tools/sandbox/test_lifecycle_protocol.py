"""Tests for sandbox lifecycle protocol types."""

import pytest

from synthorg.tools.sandbox.lifecycle.protocol import ContainerHandle

pytestmark = pytest.mark.unit


class TestContainerHandle:
    """ContainerHandle construction and validation."""

    def test_valid_handle(self) -> None:
        handle = ContainerHandle(container_id="abc123")
        assert handle.container_id == "abc123"
        assert handle.sidecar_id is None
        assert handle.network_mode == "none"

    def test_with_sidecar(self) -> None:
        handle = ContainerHandle(
            container_id="sandbox-1",
            sidecar_id="sidecar-1",
            network_mode="container:sidecar-1",
        )
        assert handle.sidecar_id == "sidecar-1"
        assert handle.network_mode == "container:sidecar-1"

    def test_frozen(self) -> None:
        handle = ContainerHandle(container_id="abc123")
        with pytest.raises(AttributeError):
            handle.container_id = "other"  # type: ignore[misc]

    def test_empty_container_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            ContainerHandle(container_id="")

    def test_whitespace_container_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            ContainerHandle(container_id="   ")

    def test_slots(self) -> None:
        handle = ContainerHandle(container_id="abc123")
        assert not hasattr(handle, "__dict__")
