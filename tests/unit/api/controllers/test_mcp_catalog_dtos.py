"""DTO validation tests for the MCP catalog controller."""

from typing import Any

import pytest
from pydantic import ValidationError

from synthorg.api.controllers.mcp_catalog import (
    InstallEntryRequest,
    InstallEntryResponse,
)


@pytest.mark.unit
class TestInstallEntryRequest:
    """Pydantic validation boundary for POST /catalog/install."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({}, id="missing_catalog_entry_id"),
            pytest.param({"catalog_entry_id": ""}, id="blank_catalog_entry_id"),
            pytest.param({"catalog_entry_id": "   "}, id="whitespace_catalog_entry_id"),
            pytest.param(
                {"catalog_entry_id": "filesystem-mcp", "connection_name": 42},
                id="non_string_connection_name",
            ),
            pytest.param(
                {"catalog_entry_id": "filesystem-mcp", "connection_name": ""},
                id="blank_connection_name",
            ),
            pytest.param(
                {"catalog_entry_id": "filesystem-mcp", "connection_name": "   "},
                id="whitespace_connection_name",
            ),
            pytest.param(
                {"catalog_entry_id": "filesystem-mcp", "unknown_field": "x"},
                id="extra_field_forbidden",
            ),
        ],
    )
    def test_rejects_invalid_payload(self, payload: dict[str, Any]) -> None:
        """DTO rejects invalid payloads at the framework boundary."""
        with pytest.raises(ValidationError):
            InstallEntryRequest(**payload)

    def test_accepts_minimal_valid_payload(self) -> None:
        req = InstallEntryRequest(catalog_entry_id="filesystem-mcp")
        assert req.catalog_entry_id == "filesystem-mcp"
        assert req.connection_name is None

    def test_accepts_full_valid_payload(self) -> None:
        req = InstallEntryRequest(
            catalog_entry_id="github-mcp",
            connection_name="my-github",
        )
        assert req.catalog_entry_id == "github-mcp"
        assert req.connection_name == "my-github"

    def test_is_frozen(self) -> None:
        req = InstallEntryRequest(catalog_entry_id="filesystem-mcp")
        with pytest.raises(ValidationError):
            req.catalog_entry_id = "other"  # type: ignore[misc]


@pytest.mark.unit
class TestInstallEntryResponse:
    """Pydantic validation boundary for the install response DTO."""

    def test_accepts_valid_payload(self) -> None:
        resp = InstallEntryResponse(
            status="installed",
            server_name="Filesystem",
            catalog_entry_id="filesystem-mcp",
            tool_count=3,
        )
        assert resp.status == "installed"
        assert resp.tool_count == 3

    def test_rejects_non_installed_status(self) -> None:
        with pytest.raises(ValidationError):
            InstallEntryResponse(
                status="pending",  # type: ignore[arg-type]
                server_name="Filesystem",
                catalog_entry_id="filesystem-mcp",
                tool_count=3,
            )

    def test_rejects_negative_tool_count(self) -> None:
        with pytest.raises(ValidationError):
            InstallEntryResponse(
                status="installed",
                server_name="Filesystem",
                catalog_entry_id="filesystem-mcp",
                tool_count=-1,
            )

    def test_rejects_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            InstallEntryResponse(
                status="installed",
                server_name="Filesystem",
                catalog_entry_id="filesystem-mcp",
                tool_count=3,
                extra_field="x",  # type: ignore[call-arg]
            )
