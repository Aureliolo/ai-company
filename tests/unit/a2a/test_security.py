"""Tests for A2A inbound security validation."""

import pytest

from synthorg.a2a.security import validate_payload_size, validate_peer


class TestValidatePeer:
    """Peer allowlist validation."""

    @pytest.mark.unit
    def test_allowed_peer(self) -> None:
        """Peer on the allowlist passes."""
        assert validate_peer("peer-a", ("peer-a", "peer-b")) is True

    @pytest.mark.unit
    def test_disallowed_peer(self) -> None:
        """Peer not on the allowlist fails."""
        assert validate_peer("unknown", ("peer-a",)) is False

    @pytest.mark.unit
    def test_empty_allowlist(self) -> None:
        """Empty allowlist rejects all peers."""
        assert validate_peer("peer-a", ()) is False

    @pytest.mark.unit
    def test_case_sensitive(self) -> None:
        """Peer names are case-sensitive."""
        assert validate_peer("Peer-A", ("peer-a",)) is False


class TestValidatePayloadSize:
    """Payload size limit validation."""

    @pytest.mark.unit
    def test_within_limit(self) -> None:
        """Payload under the limit passes."""
        assert validate_payload_size(b"x" * 100, 1024) is True

    @pytest.mark.unit
    def test_at_limit(self) -> None:
        """Payload exactly at the limit passes."""
        assert validate_payload_size(b"x" * 1024, 1024) is True

    @pytest.mark.unit
    def test_over_limit(self) -> None:
        """Payload over the limit fails."""
        assert validate_payload_size(b"x" * 1025, 1024) is False

    @pytest.mark.unit
    def test_empty_body(self) -> None:
        """Empty body always passes."""
        assert validate_payload_size(b"", 1024) is True
