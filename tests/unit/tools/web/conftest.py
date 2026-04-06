"""Shared fixtures for web tool tests."""

import pytest

from synthorg.tools.network_validator import NetworkPolicy
from synthorg.tools.web.html_parser import HtmlParserTool
from synthorg.tools.web.http_request import HttpRequestTool
from synthorg.tools.web.web_search import SearchResult


class MockSearchProvider:
    """Mock web search provider for testing."""

    def __init__(
        self,
        *,
        results: list[SearchResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._results = results or []
        self._error = error

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        if self._error:
            raise self._error
        return self._results[:max_results]


@pytest.fixture
def permissive_policy() -> NetworkPolicy:
    """Policy that allows all IPs (for testing HTTP logic)."""
    return NetworkPolicy(block_private_ips=False)


@pytest.fixture
def http_tool(permissive_policy: NetworkPolicy) -> HttpRequestTool:
    return HttpRequestTool(network_policy=permissive_policy)


@pytest.fixture
def html_tool() -> HtmlParserTool:
    return HtmlParserTool()


@pytest.fixture
def mock_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Test Result 1",
            url="https://example.com/1",
            snippet="First result snippet",
        ),
        SearchResult(
            title="Test Result 2",
            url="https://example.com/2",
            snippet="Second result snippet",
        ),
    ]
