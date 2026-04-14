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
            "message/stream",
            "tasks/get",
            "tasks/cancel",
        }
        assert expected == _SUPPORTED_METHODS
