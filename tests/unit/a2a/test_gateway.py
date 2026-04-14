"""Tests for the A2A JSON-RPC 2.0 gateway controller helpers."""

from typing import ClassVar

import pytest

from synthorg.a2a.gateway import (
    _error_response,
    _extract_peer_name,
    _success_response,
)
from synthorg.a2a.models import (
    A2A_PEER_NOT_ALLOWED,
    JSONRPC_METHOD_NOT_FOUND,
)


class TestErrorResponse:
    """JSON-RPC error response builder."""

    @pytest.mark.unit
    def test_structure(self) -> None:
        """Error response has correct JSON-RPC structure."""
        resp = _error_response(
            "req-1",
            JSONRPC_METHOD_NOT_FOUND,
            "Method not found",
        )
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == "req-1"
        assert resp["error"]["code"] == -32601
        assert resp["error"]["message"] == "Method not found"
        assert resp["result"] is None

    @pytest.mark.unit
    def test_with_data(self) -> None:
        """Error response can carry additional data."""
        resp = _error_response(
            "req-1",
            A2A_PEER_NOT_ALLOWED,
            "Not allowed",
            data={"peer": "unknown"},
        )
        assert resp["error"]["data"]["peer"] == "unknown"

    @pytest.mark.unit
    def test_null_id(self) -> None:
        """Error response with null id (parse errors)."""
        resp = _error_response(None, -32700, "Parse error")
        assert resp["id"] is None


class TestSuccessResponse:
    """JSON-RPC success response builder."""

    @pytest.mark.unit
    def test_structure(self) -> None:
        """Success response has correct JSON-RPC structure."""
        resp = _success_response("req-1", {"status": "ok"})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == "req-1"
        assert resp["result"]["status"] == "ok"
        assert resp["error"] is None


class TestExtractPeerName:
    """Peer name extraction from request headers."""

    @pytest.mark.unit
    def test_from_header(self) -> None:
        """Extracts peer name from X-A2A-Peer-Name header."""

        class FakeRequest:
            headers: ClassVar[dict[str, str]] = {
                "x-a2a-peer-name": "peer-alpha",
            }

        result = _extract_peer_name(FakeRequest())  # type: ignore[arg-type]
        assert result == "peer-alpha"

    @pytest.mark.unit
    def test_strips_whitespace(self) -> None:
        """Strips whitespace from peer name."""

        class FakeRequest:
            headers: ClassVar[dict[str, str]] = {
                "x-a2a-peer-name": "  peer-beta  ",
            }

        result = _extract_peer_name(FakeRequest())  # type: ignore[arg-type]
        assert result == "peer-beta"

    @pytest.mark.unit
    def test_missing_header(self) -> None:
        """Returns None when header is absent."""

        class FakeRequest:
            headers: ClassVar[dict[str, str]] = {}

        result = _extract_peer_name(FakeRequest())  # type: ignore[arg-type]
        assert result is None


class TestSupportedMethods:
    """Verify supported method set."""

    @pytest.mark.unit
    def test_all_methods(self) -> None:
        """All expected methods are in the supported set."""
        from synthorg.a2a.gateway import _SUPPORTED_METHODS

        expected = {
            "message/send",
            "tasks/get",
            "tasks/cancel",
        }
        assert expected == _SUPPORTED_METHODS


class TestMethodHandlers:
    """Method handler registration."""

    @pytest.mark.unit
    def test_handler_registry_matches_supported_methods(self) -> None:
        """Every supported method has a registered handler."""
        from synthorg.a2a.gateway import _METHOD_HANDLERS, _SUPPORTED_METHODS

        assert set(_METHOD_HANDLERS.keys()) == _SUPPORTED_METHODS

    @pytest.mark.unit
    def test_handler_functions_are_callable(self) -> None:
        """All handler values are async callables."""
        from synthorg.a2a.gateway import _METHOD_HANDLERS

        for method, handler in _METHOD_HANDLERS.items():
            assert callable(handler), f"Handler for {method} is not callable"


class TestParseJsonrpc:
    """JSON-RPC request parsing."""

    @pytest.mark.unit
    def test_valid_request(self) -> None:
        """Valid JSON-RPC request is parsed successfully."""
        from synthorg.a2a.gateway import _parse_jsonrpc

        body = b'{"jsonrpc":"2.0","id":"1","method":"message/send","params":{}}'
        result = _parse_jsonrpc(body)
        assert result is not None
        assert result.method == "message/send"

    @pytest.mark.unit
    def test_invalid_json(self) -> None:
        """Invalid JSON returns None."""
        from synthorg.a2a.gateway import _parse_jsonrpc

        result = _parse_jsonrpc(b"not json {{{")
        assert result is None

    @pytest.mark.unit
    def test_missing_method(self) -> None:
        """Missing method field returns None."""
        from synthorg.a2a.gateway import _parse_jsonrpc

        result = _parse_jsonrpc(b'{"jsonrpc":"2.0","id":"1","params":{}}')
        assert result is None

    @pytest.mark.unit
    def test_empty_body(self) -> None:
        """Empty body returns None."""
        from synthorg.a2a.gateway import _parse_jsonrpc

        result = _parse_jsonrpc(b"")
        assert result is None


class TestA2AMethodError:
    """Internal method error."""

    @pytest.mark.unit
    def test_default_http_status(self) -> None:
        """Default HTTP status is 400."""
        from synthorg.a2a.gateway import _A2AMethodError

        err = _A2AMethodError(-32602, "Invalid params")
        assert err.http_status == 400
        assert err.code == -32602
        assert err.message == "Invalid params"

    @pytest.mark.unit
    def test_custom_http_status(self) -> None:
        """Custom HTTP status is respected."""
        from synthorg.a2a.gateway import _A2AMethodError

        err = _A2AMethodError(-32001, "Not found", http_status=404)
        assert err.http_status == 404


class TestValidateTaskOwnership:
    """Task ownership validation stub."""

    @pytest.mark.unit
    def test_ownership_check_is_noop(self) -> None:
        """Phase 1: ownership check accepts any authenticated peer."""
        from synthorg.a2a.gateway import _validate_task_ownership

        # Should not raise
        _validate_task_ownership(object(), "any-peer")
