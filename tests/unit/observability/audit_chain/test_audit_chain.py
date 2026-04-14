"""Tests for the audit chain module."""

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from synthorg.observability.audit_chain.chain import HashChain
from synthorg.observability.audit_chain.config import AuditChainConfig
from synthorg.observability.audit_chain.protocol import (
    AuditChainSigner,
    SignedPayload,
)
from synthorg.observability.audit_chain.sink import AuditChainSink
from synthorg.observability.audit_chain.timestamping import (
    LocalClockProvider,
    ResilientTimestampProvider,
)
from synthorg.observability.audit_chain.verifier import (
    AuditChainVerifier,
)


def _make_mock_signer() -> AsyncMock:
    """Create a mock AuditChainSigner."""
    signer = AsyncMock(spec=AuditChainSigner)
    signer.algorithm = "test-algo"
    signer.sign = AsyncMock(
        return_value=SignedPayload(
            signature=b"test-sig",
            algorithm="test-algo",
            signer_id="test-signer",
            signed_at=datetime.now(UTC),
        ),
    )
    signer.verify = AsyncMock(return_value=True)
    return signer


# ── Config Tests ───────────────────────────────────────────────────


@pytest.mark.unit
class TestAuditChainConfig:
    """Tests for AuditChainConfig defaults."""

    def test_defaults(self) -> None:
        config = AuditChainConfig()
        assert config.enabled is False
        assert config.backend == "asqav"
        assert config.tsa_url is None
        assert config.signing_key_path is None

    def test_frozen(self) -> None:
        config = AuditChainConfig()
        with pytest.raises(ValidationError):
            config.enabled = True  # type: ignore[misc]


# ── Protocol Tests ─────────────────────────────────────────────────


@pytest.mark.unit
class TestSignedPayload:
    """Tests for SignedPayload model."""

    def test_construction(self) -> None:
        payload = SignedPayload(
            signature=b"sig",
            algorithm="ml-dsa-65",
            signer_id="signer-1",
            signed_at=datetime.now(UTC),
        )
        assert payload.algorithm == "ml-dsa-65"
        assert payload.signature == b"sig"

    def test_frozen(self) -> None:
        payload = SignedPayload(
            signature=b"sig",
            algorithm="ml-dsa-65",
            signer_id="signer-1",
            signed_at=datetime.now(UTC),
        )
        with pytest.raises(ValidationError):
            payload.algorithm = "ed25519"  # type: ignore[misc]


@pytest.mark.unit
class TestAuditChainSignerProtocol:
    """Tests for AuditChainSigner protocol."""

    def test_mock_satisfies_protocol(self) -> None:
        signer = _make_mock_signer()
        assert isinstance(signer, AuditChainSigner)


# ── HashChain Tests ────────────────────────────────────────────────


@pytest.mark.unit
class TestHashChain:
    """Tests for HashChain append and verify."""

    def test_empty_chain_verifies(self) -> None:
        chain = HashChain()
        assert chain.verify_integrity() is True
        assert len(chain.entries) == 0

    def test_append_creates_entry(self) -> None:
        chain = HashChain()
        entry = chain.append(
            event_data=b"event-1",
            signature=b"sig-1",
            timestamp=datetime.now(UTC),
        )
        assert entry.position == 0
        assert entry.previous_hash == "genesis"
        assert len(chain.entries) == 1

    def test_chain_links_entries(self) -> None:
        chain = HashChain()
        chain.append(b"event-1", b"sig-1", datetime.now(UTC))
        entry2 = chain.append(b"event-2", b"sig-2", datetime.now(UTC))
        assert entry2.position == 1
        assert entry2.previous_hash != "genesis"

    def test_chain_verifies_after_multiple_appends(self) -> None:
        chain = HashChain()
        for i in range(10):
            chain.append(
                f"event-{i}".encode(),
                f"sig-{i}".encode(),
                datetime.now(UTC),
            )
        assert chain.verify_integrity() is True

    def test_tampered_chain_fails_verification(self) -> None:
        chain = HashChain()
        chain.append(b"event-1", b"sig-1", datetime.now(UTC))
        chain.append(b"event-2", b"sig-2", datetime.now(UTC))
        # Tamper: modify the previous_hash of entry 1.
        tampered = chain._entries[1].model_copy(
            update={"previous_hash": "tampered"},
        )
        chain._entries[1] = tampered
        assert chain.verify_integrity() is False


# ── Timestamping Tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestLocalClockProvider:
    """Tests for LocalClockProvider."""

    async def test_returns_utc_datetime(self) -> None:
        provider = LocalClockProvider()
        ts = await provider.get_timestamp()
        assert ts.tzinfo is not None


@pytest.mark.unit
class TestResilientTimestampProvider:
    """Tests for ResilientTimestampProvider fallback."""

    async def test_fallback_to_local_on_tsa_error(self) -> None:
        """TSA failure falls back to local clock."""
        provider = ResilientTimestampProvider(tsa_url="https://tsa.example.com")
        # TSA is not implemented, so it will raise NotImplementedError
        # and fall back to local clock.
        ts = await provider.get_timestamp()
        assert ts.tzinfo is not None


# ── Sink Tests ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestAuditChainSink:
    """Tests for AuditChainSink logging handler."""

    def test_filters_non_security_events(self) -> None:
        signer = _make_mock_signer()
        provider = LocalClockProvider()
        chain = HashChain()
        sink = AuditChainSink(
            signer=signer,
            timestamp_provider=provider,
            chain=chain,
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="tool.invoke.start",
            args=(),
            exc_info=None,
        )
        sink.emit(record)
        assert len(chain.entries) == 0

    def test_signs_security_events(self) -> None:
        signer = _make_mock_signer()
        provider = LocalClockProvider()
        chain = HashChain()
        sink = AuditChainSink(
            signer=signer,
            timestamp_provider=provider,
            chain=chain,
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="security.verdict.allow",
            args=(),
            exc_info=None,
        )
        sink.emit(record)
        assert len(chain.entries) == 1

    def test_multiple_security_events_chain(self) -> None:
        signer = _make_mock_signer()
        provider = LocalClockProvider()
        chain = HashChain()
        sink = AuditChainSink(
            signer=signer,
            timestamp_provider=provider,
            chain=chain,
        )
        for i in range(5):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"security.event.{i}",
                args=(),
                exc_info=None,
            )
            sink.emit(record)
        assert len(chain.entries) == 5
        assert chain.verify_integrity() is True


# ── Verifier Tests ─────────────────────────────────────────────────


@pytest.mark.unit
class TestAuditChainVerifier:
    """Tests for AuditChainVerifier."""

    async def test_empty_chain_valid(self) -> None:
        signer = _make_mock_signer()
        verifier = AuditChainVerifier(signer=signer)
        chain = HashChain()
        result = await verifier.verify_chain(chain)
        assert result.valid is True
        assert result.entries_checked == 0

    async def test_valid_chain_passes(self) -> None:
        signer = _make_mock_signer()
        verifier = AuditChainVerifier(signer=signer)
        chain = HashChain()
        for i in range(5):
            chain.append(
                f"event-{i}".encode(),
                b"sig",
                datetime.now(UTC),
            )
        result = await verifier.verify_chain(chain)
        assert result.valid is True
        assert result.entries_checked == 5

    async def test_broken_chain_detected(self) -> None:
        signer = _make_mock_signer()
        verifier = AuditChainVerifier(signer=signer)
        chain = HashChain()
        chain.append(b"event-1", b"sig", datetime.now(UTC))
        chain.append(b"event-2", b"sig", datetime.now(UTC))
        # Tamper.
        tampered = chain._entries[1].model_copy(
            update={"previous_hash": "tampered"},
        )
        chain._entries[1] = tampered

        result = await verifier.verify_chain(chain)
        assert result.valid is False
        assert result.first_break_position == 1


# ── Property Tests ─────────────────────────────────────────────────


@pytest.mark.unit
class TestHashChainProperties:
    """Property-based tests for HashChain."""

    @given(n=st.integers(min_value=1, max_value=20))
    @settings(max_examples=20)
    def test_untampered_chain_always_verifies(self, n: int) -> None:
        chain = HashChain()
        for i in range(n):
            chain.append(
                f"event-{i}".encode(),
                f"sig-{i}".encode(),
                datetime.now(UTC),
            )
        assert chain.verify_integrity() is True
        assert len(chain.entries) == n
