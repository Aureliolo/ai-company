"""Unit tests for the MCP server catalog."""

import pytest

from synthorg.integrations.errors import CatalogEntryNotFoundError
from synthorg.integrations.mcp_catalog.service import CatalogService


@pytest.mark.unit
class TestCatalogService:
    """Tests for the bundled MCP catalog service."""

    async def test_browse_returns_entries(self) -> None:
        service = CatalogService()
        entries = await service.browse()
        assert len(entries) >= 8

    async def test_browse_entries_have_required_fields(self) -> None:
        service = CatalogService()
        entries = await service.browse()
        for entry in entries:
            assert entry.id
            assert entry.name
            assert entry.transport

    async def test_search_by_name(self) -> None:
        service = CatalogService()
        results = await service.search("github")
        assert len(results) >= 1
        assert any(e.id == "github-mcp" for e in results)

    async def test_search_by_tag(self) -> None:
        service = CatalogService()
        results = await service.search("database")
        assert len(results) >= 1

    async def test_search_case_insensitive(self) -> None:
        service = CatalogService()
        results = await service.search("SLACK")
        assert len(results) >= 1

    async def test_search_no_results(self) -> None:
        service = CatalogService()
        results = await service.search("zzz_nonexistent_zzz")
        assert len(results) == 0

    async def test_get_entry_found(self) -> None:
        service = CatalogService()
        entry = await service.get_entry("github-mcp")
        assert entry.name == "GitHub"

    async def test_get_entry_not_found(self) -> None:
        service = CatalogService()
        with pytest.raises(CatalogEntryNotFoundError):
            await service.get_entry("nonexistent")
