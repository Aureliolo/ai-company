"""Tests for request middleware (CSP and logging)."""

from typing import Any

import pytest
from litestar.testing import TestClient  # noqa: TC002

from ai_company.api.middleware import (
    _API_CSP,
    _DOCS_CSP,
    CSPMiddleware,
)


async def _fake_app(scope: Any, receive: Any, send: Any) -> None:
    """Minimal ASGI app that returns a 200 response."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        }
    )
    await send({"type": "http.response.body", "body": b""})


def _make_scope(path: str) -> dict[str, Any]:
    """Build a minimal ASGI HTTP scope for testing."""
    return {
        "type": "http",
        "path": path,
        "method": "GET",
        "headers": [],
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "server": ("localhost", 8000),
    }


@pytest.mark.unit
class TestCSPMiddleware:
    """Tests for path-aware Content-Security-Policy middleware."""

    def test_api_route_gets_strict_csp(self, test_client: TestClient[Any]) -> None:
        response = test_client.get("/api/v1/health")
        csp = response.headers.get("content-security-policy")
        assert csp == _API_CSP

    def test_docs_route_gets_relaxed_csp(self, test_client: TestClient[Any]) -> None:
        response = test_client.get("/docs/api")
        csp = response.headers.get("content-security-policy")
        assert csp == _DOCS_CSP

    def test_docs_exact_path_gets_relaxed_csp(
        self, test_client: TestClient[Any]
    ) -> None:
        response = test_client.get("/docs")
        csp = response.headers.get("content-security-policy")
        assert csp == _DOCS_CSP

    async def test_unrelated_docs_prefix_gets_strict_csp(self) -> None:
        """Paths like /documents should NOT get the relaxed CSP."""
        middleware = CSPMiddleware(_fake_app)
        captured: list[dict[str, Any]] = []

        async def capture_send(message: Any) -> None:
            captured.append(message)

        await middleware(_make_scope("/documents"), None, capture_send)  # type: ignore[arg-type]

        start_msg = captured[0]
        headers = dict(start_msg["headers"])
        assert headers[b"content-security-policy"] == _API_CSP.encode()

    async def test_docsearch_prefix_gets_strict_csp(self) -> None:
        """Paths like /docsearch should NOT get the relaxed CSP."""
        middleware = CSPMiddleware(_fake_app)
        captured: list[dict[str, Any]] = []

        async def capture_send(message: Any) -> None:
            captured.append(message)

        await middleware(_make_scope("/docsearch"), None, capture_send)  # type: ignore[arg-type]

        start_msg = captured[0]
        headers = dict(start_msg["headers"])
        assert headers[b"content-security-policy"] == _API_CSP.encode()

    async def test_docs_subpath_gets_relaxed_csp(self) -> None:
        """Paths like /docs/api should get the relaxed CSP."""
        middleware = CSPMiddleware(_fake_app)
        captured: list[dict[str, Any]] = []

        async def capture_send(message: Any) -> None:
            captured.append(message)

        await middleware(_make_scope("/docs/api"), None, capture_send)  # type: ignore[arg-type]

        start_msg = captured[0]
        headers = dict(start_msg["headers"])
        assert headers[b"content-security-policy"] == _DOCS_CSP.encode()

    async def test_non_http_scope_passes_through(self) -> None:
        """Non-HTTP scopes should not get CSP headers."""
        called = False

        async def passthrough_app(scope: Any, receive: Any, send: Any) -> None:
            nonlocal called
            called = True

        middleware = CSPMiddleware(passthrough_app)
        await middleware({"type": "lifespan"}, None, None)  # type: ignore[arg-type]
        assert called


@pytest.mark.unit
class TestRequestLoggingMiddleware:
    def test_request_completes_with_status(self, test_client: TestClient[Any]) -> None:
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200

    def test_not_found_returns_correct_status(
        self, test_client: TestClient[Any]
    ) -> None:
        response = test_client.get("/api/v1/agents/nonexistent")
        assert response.status_code == 404
