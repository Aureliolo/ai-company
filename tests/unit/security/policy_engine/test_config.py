"""Tests for SecurityPolicyConfig and factory."""

import pytest
from pydantic import ValidationError

from synthorg.security.policy_engine.config import (
    SecurityPolicyConfig,
    build_policy_engine,
)


@pytest.mark.unit
class TestSecurityPolicyConfig:
    """Tests for SecurityPolicyConfig defaults and validation."""

    def test_defaults(self) -> None:
        config = SecurityPolicyConfig()
        assert config.engine == "none"
        assert config.policy_files == ()
        assert config.evaluation_mode == "log_only"
        assert config.fail_closed is False

    def test_frozen(self) -> None:
        config = SecurityPolicyConfig()
        with pytest.raises(ValidationError):
            config.engine = "cedar"  # type: ignore[misc]

    def test_cedar_engine_requires_policy_files(self) -> None:
        with pytest.raises(ValueError, match="policy_files"):
            SecurityPolicyConfig(engine="cedar")

    def test_cedar_engine_with_files(self, tmp_path: object) -> None:
        from pathlib import Path

        p = Path(str(tmp_path)) / "policy.cedar"
        p.write_text("permit(principal, action, resource);")
        config = SecurityPolicyConfig(engine="cedar", policy_files=(p,))
        assert config.engine == "cedar"

    def test_invalid_engine_rejected(self) -> None:
        with pytest.raises(ValueError, match="Input should be"):
            SecurityPolicyConfig(engine="invalid")  # type: ignore[arg-type]

    def test_invalid_evaluation_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="Input should be"):
            SecurityPolicyConfig(evaluation_mode="block")  # type: ignore[arg-type]


@pytest.mark.unit
class TestBuildPolicyEngine:
    """Tests for build_policy_engine factory."""

    def test_returns_none_for_none_engine(self) -> None:
        config = SecurityPolicyConfig(engine="none")
        engine = build_policy_engine(config)
        assert engine is None

    def test_cedar_without_files_raises_at_config(self) -> None:
        """Cedar without policy_files is rejected at config construction."""
        with pytest.raises(ValueError, match="policy_files"):
            SecurityPolicyConfig(engine="cedar", policy_files=())
