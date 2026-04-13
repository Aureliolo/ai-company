"""Tests for EvolverConfig safety rails."""

import pytest
from pydantic import ValidationError

from synthorg.memory.procedural.evolver_config import EvolverConfig


@pytest.mark.unit
class TestEvolverConfig:
    def test_defaults(self) -> None:
        config = EvolverConfig()
        assert config.enabled is False
        assert config.min_confidence_for_org_promotion == 0.8
        assert config.min_agents_seen_pattern == 3
        assert config.max_proposals_per_cycle == 10
        assert config.max_org_entries == 10000
        assert config.requires_human_approval is True

    def test_enabled(self) -> None:
        config = EvolverConfig(enabled=True)
        assert config.enabled is True

    def test_custom_thresholds(self) -> None:
        config = EvolverConfig(
            min_confidence_for_org_promotion=0.9,
            min_agents_seen_pattern=5,
            max_proposals_per_cycle=20,
        )
        assert config.min_confidence_for_org_promotion == 0.9
        assert config.min_agents_seen_pattern == 5
        assert config.max_proposals_per_cycle == 20

    def test_requires_human_approval_cannot_be_false(self) -> None:
        """Literal[True] structurally prevents False."""
        with pytest.raises(ValidationError):
            EvolverConfig(requires_human_approval=False)  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        config = EvolverConfig()
        with pytest.raises(ValidationError):
            config.enabled = True  # type: ignore[misc]

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            EvolverConfig(min_confidence_for_org_promotion=1.5)

    def test_min_agents_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolverConfig(min_agents_seen_pattern=0)
