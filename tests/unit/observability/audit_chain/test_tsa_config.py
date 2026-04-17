"""Unit tests for AuditChainConfig TSA preset coherence (#1412)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from synthorg.observability.audit_chain.config import (
    AuditChainConfig,
    TsaPreset,
    resolve_tsa_url,
)

pytestmark = pytest.mark.unit


def test_default_preset_is_none() -> None:
    config = AuditChainConfig()
    assert config.tsa_preset == TsaPreset.NONE
    assert config.tsa_url is None
    assert config.effective_tsa_url is None


def test_custom_preset_requires_tsa_url() -> None:
    with pytest.raises(ValidationError, match="requires tsa_url"):
        AuditChainConfig(tsa_preset=TsaPreset.CUSTOM)


def test_custom_preset_with_url_resolves() -> None:
    config = AuditChainConfig(
        tsa_preset=TsaPreset.CUSTOM,
        tsa_url="https://tsa.example.com/tsr",
        tsa_trusted_roots_path=Path("tests/data/custom_roots.pem"),
    )
    assert config.effective_tsa_url == "https://tsa.example.com/tsr"


def test_freetsa_preset_resolves_to_canonical_url() -> None:
    config = AuditChainConfig(
        tsa_preset=TsaPreset.FREETSA,
        tsa_trusted_roots_path=Path("tests/data/freetsa_roots.pem"),
    )
    assert config.effective_tsa_url == "https://freetsa.org/tsr"


@pytest.mark.parametrize(
    "tsa_preset",
    [TsaPreset.FREETSA, TsaPreset.DIGICERT, TsaPreset.SECTIGO],
)
def test_tsa_missing_roots_rejected_when_verifying(tsa_preset: TsaPreset) -> None:
    """Verifying presets reject configs without ``tsa_trusted_roots_path``."""
    with pytest.raises(ValidationError, match="tsa_trusted_roots_path"):
        AuditChainConfig(
            tsa_preset=tsa_preset,
            tsa_verify_signature=True,
        )


def test_freetsa_without_roots_allowed_when_not_verifying() -> None:
    config = AuditChainConfig(
        tsa_preset=TsaPreset.FREETSA,
        tsa_verify_signature=False,
    )
    assert config.effective_tsa_url == "https://freetsa.org/tsr"


def test_custom_tsa_url_overrides_preset() -> None:
    """A non-NONE non-CUSTOM preset with tsa_url uses the override."""
    config = AuditChainConfig(
        tsa_preset=TsaPreset.DIGICERT,
        tsa_url="https://staging-tsa.example.com/tsr",
        tsa_trusted_roots_path=Path("tests/data/digicert_roots.pem"),
    )
    assert config.effective_tsa_url == "https://staging-tsa.example.com/tsr"


def test_digicert_preset_resolves_default() -> None:
    config = AuditChainConfig(
        tsa_preset=TsaPreset.DIGICERT,
        tsa_trusted_roots_path=Path("tests/data/digicert_roots.pem"),
    )
    assert config.effective_tsa_url == "http://timestamp.digicert.com"


def test_sectigo_preset_resolves_default() -> None:
    config = AuditChainConfig(
        tsa_preset=TsaPreset.SECTIGO,
        tsa_trusted_roots_path=Path("tests/data/sectigo_roots.pem"),
    )
    assert config.effective_tsa_url == "http://timestamp.sectigo.com"


def test_custom_without_roots_rejected_when_verifying() -> None:
    with pytest.raises(ValidationError, match="tsa_trusted_roots_path"):
        AuditChainConfig(
            tsa_preset=TsaPreset.CUSTOM,
            tsa_url="https://tsa.example.com/tsr",
            tsa_verify_signature=True,
        )


def test_timeout_range_enforced() -> None:
    with pytest.raises(ValidationError):
        AuditChainConfig(tsa_timeout_sec=0.0)
    with pytest.raises(ValidationError):
        AuditChainConfig(tsa_timeout_sec=60.0)


@pytest.mark.parametrize("value", [0.1, 2.5, 5.0])
def test_timeout_accepts_boundary_values(value: float) -> None:
    """The validator permits values in the allowed ``(0, 60)`` range."""
    cfg = AuditChainConfig(tsa_timeout_sec=value)
    assert cfg.tsa_timeout_sec == value


def test_resolve_tsa_url_helper() -> None:
    assert resolve_tsa_url(TsaPreset.NONE, None) is None
    assert resolve_tsa_url(TsaPreset.NONE, "override") is None
    assert resolve_tsa_url(TsaPreset.CUSTOM, "x") == "x"
    assert resolve_tsa_url(TsaPreset.CUSTOM, None) is None
    assert resolve_tsa_url(TsaPreset.DIGICERT, None) == (
        "http://timestamp.digicert.com"
    )
    assert resolve_tsa_url(TsaPreset.FREETSA, "override") == "override"
