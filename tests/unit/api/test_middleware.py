"""Tests for request middleware and security headers hook."""

from typing import Any

import pytest
from litestar import Litestar, get, post
from litestar.enums import ScopeType
from litestar.exceptions import ValidationException
from litestar.testing import TestClient

from synthorg.api.exception_handlers import EXCEPTION_HANDLERS
from synthorg.api.middleware import (
    _API_CSP,
    _DOCS_CSP,
    _SECURITY_HEADERS,
    security_headers_hook,
)


def _make_app(*handlers: Any) -> Litestar:
    """Build a minimal Litestar app with the security hook wired in."""
    return Litestar(
        route_handlers=list(handlers),
        before_send=[security_headers_hook],
        exception_handlers=EXCEPTION_HANDLERS,  # type: ignore[arg-type]
    )


def _assert_all_security_headers(
    resp: Any,
    *,
    status: int,
) -> None:
    """Assert that all static security headers and CSP are present.

    Only valid for non-docs paths (where COOP is ``same-origin``
    and CSP is the strict API policy).
    """
    for name, expected in _SECURITY_HEADERS.items():
        assert resp.headers.get(name) == expected, (
            f"Missing or wrong header on {status}: {name}"
        )
    # CSP must also be present (strict for non-docs paths).
    assert resp.headers.get("content-security-policy") == _API_CSP, (
        f"Missing or wrong CSP on {status}"
    )


# ── Security headers hook ──────────────────────────────────────


@pytest.mark.unit
class TestSecurityHeadersHook:
    """Verify security headers appear on ALL response types."""

    def test_success_response_has_all_security_headers(self) -> None:
        """200 OK carries every static security header and CSP."""

        @get("/ok")
        async def handler() -> dict[str, str]:
            return {"status": "ok"}

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/ok")
            assert resp.status_code == 200
            _assert_all_security_headers(resp, status=200)

    def test_exception_handler_response_has_security_headers(
        self,
    ) -> None:
        """Exception-handler 400 carries all security headers."""

        @get("/fail")
        async def handler() -> None:
            raise ValidationException

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/fail")
            assert resp.status_code == 400
            _assert_all_security_headers(resp, status=400)

    def test_unmatched_route_404_has_security_headers(self) -> None:
        """Router-level 404 (no matching route) carries headers."""

        @get("/exists")
        async def handler() -> str:
            return "ok"

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/nonexistent")
            assert resp.status_code == 404
            _assert_all_security_headers(resp, status=404)

    def test_method_not_allowed_405_has_security_headers(self) -> None:
        """Router-level 405 carries security headers."""

        @post("/only-post")
        async def handler() -> str:
            return "ok"

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/only-post")
            assert resp.status_code == 405
            _assert_all_security_headers(resp, status=405)

    def test_500_error_has_security_headers(self) -> None:
        """Unexpected error 500 carries security headers."""

        @get("/boom")
        async def handler() -> None:
            msg = "unexpected"
            raise RuntimeError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/boom")
            assert resp.status_code == 500
            _assert_all_security_headers(resp, status=500)

    async def test_non_http_scope_is_skipped(self) -> None:
        """Non-HTTP scopes (WebSocket, lifespan) are not modified."""
        message: Any = {
            "type": "websocket.connect",
            "headers": [],
        }
        scope: Any = {"type": ScopeType.WEBSOCKET}

        await security_headers_hook(message, scope)

        # Headers list should remain empty — hook returned early.
        assert message.get("headers") == []


# ── CSP path selection ─────────────────────────────────────────


@pytest.mark.unit
class TestCSPPathSelection:
    """Verify path-aware CSP via the before_send hook."""

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

    @pytest.mark.parametrize(
        ("path", "expected_csp"),
        [
            ("/documents", _API_CSP),
            ("/docsearch", _API_CSP),
            ("/docs/api", _DOCS_CSP),
            ("/docs/openapi.json", _DOCS_CSP),
        ],
        ids=[
            "documents-strict",
            "docsearch-strict",
            "docs-subpath-relaxed",
            "docs-openapi-relaxed",
        ],
    )
    def test_csp_path_boundary(
        self,
        test_client: TestClient[Any],
        path: str,
        expected_csp: str,
    ) -> None:
        """Verify CSP assignment for boundary paths."""
        response = test_client.get(path)
        csp = response.headers.get("content-security-policy")
        assert csp == expected_csp

    def test_docs_path_relaxes_coop(self, test_client: TestClient[Any]) -> None:
        """Docs paths get COOP unsafe-none for Scalar UI compatibility."""
        response = test_client.get("/docs/openapi.json")
        assert response.headers.get("cross-origin-opener-policy") == "unsafe-none"

    def test_api_path_keeps_strict_coop(self, test_client: TestClient[Any]) -> None:
        """API paths keep COOP same-origin."""
        response = test_client.get("/api/v1/health")
        assert response.headers.get("cross-origin-opener-policy") == "same-origin"


# ── Request logging middleware ─────────────────────────────────


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
