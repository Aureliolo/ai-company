"""Tests for WorkflowVersionService."""

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.workflow.version_service import WorkflowVersionService


def _service(repo: AsyncMock | None = None) -> WorkflowVersionService:
    return WorkflowVersionService(version_repo=repo or AsyncMock())


class TestListVersions:
    @pytest.mark.unit
    async def test_returns_page_and_total(self) -> None:
        repo = AsyncMock()
        repo.count_versions.return_value = 7
        repo.list_versions.return_value = ("snapshot-a", "snapshot-b")
        service = _service(repo)
        page, total = await service.list_versions(
            NotBlankStr("wfdef-1"),
            offset=0,
            limit=2,
        )
        assert total == 7
        assert cast("tuple[Any, ...]", page) == ("snapshot-a", "snapshot-b")
        repo.list_versions.assert_awaited_once_with(
            NotBlankStr("wfdef-1"),
            limit=2,
            offset=0,
        )

    @pytest.mark.unit
    async def test_invalid_offset_rejected(self) -> None:
        service = _service()
        with pytest.raises(ValueError, match="offset"):
            await service.list_versions(
                NotBlankStr("wfdef-1"),
                offset=-1,
                limit=10,
            )

    @pytest.mark.unit
    async def test_invalid_limit_rejected(self) -> None:
        service = _service()
        with pytest.raises(ValueError, match="limit"):
            await service.list_versions(
                NotBlankStr("wfdef-1"),
                offset=0,
                limit=0,
            )


class TestGetVersion:
    @pytest.mark.unit
    async def test_returns_snapshot(self) -> None:
        repo = AsyncMock()
        repo.get_version.return_value = "snapshot-1"
        service = _service(repo)
        result = await service.get_version(NotBlankStr("wfdef-1"), 3)
        assert cast("Any", result) == "snapshot-1"
        repo.get_version.assert_awaited_once_with(NotBlankStr("wfdef-1"), 3)

    @pytest.mark.unit
    async def test_invalid_revision_rejected(self) -> None:
        service = _service()
        with pytest.raises(ValueError, match="revision"):
            await service.get_version(NotBlankStr("wfdef-1"), 0)
