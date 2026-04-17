"""Tests for evaluation framework configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.hr.evaluation.config import (
    EfficiencyConfig,
    EvaluationConfig,
    ExperienceConfig,
    GovernanceConfig,
    IntelligenceConfig,
    ResilienceConfig,
)

pytestmark = pytest.mark.unit


class TestIntelligenceConfig:
    """IntelligenceConfig tests."""

    def test_defaults(self) -> None:
        cfg = IntelligenceConfig()
        assert cfg.enabled is True
        assert cfg.weight == 0.2
        assert cfg.ci_quality_enabled is True
        assert cfg.llm_calibration_enabled is True
        assert cfg.ci_quality_weight == 0.7
        assert cfg.llm_calibration_weight == 0.3

    def test_frozen(self) -> None:
        cfg = IntelligenceConfig()
        with pytest.raises(ValidationError):
            cfg.enabled = False  # type: ignore[misc]

    def test_disable_metric(self) -> None:
        cfg = IntelligenceConfig(llm_calibration_enabled=False)
        assert cfg.llm_calibration_enabled is False
        assert cfg.ci_quality_enabled is True


class TestEfficiencyConfig:
    """EfficiencyConfig tests."""

    def test_defaults(self) -> None:
        cfg = EfficiencyConfig()
        assert cfg.enabled is True
        assert cfg.cost_enabled is True
        assert cfg.time_enabled is True
        assert cfg.tokens_enabled is True
        assert cfg.reference_cost == 10.0
        assert cfg.reference_time_seconds == 300.0
        assert cfg.reference_tokens == 5000

    def test_custom_references(self) -> None:
        cfg = EfficiencyConfig(
            reference_cost=50.0,
            reference_time_seconds=600.0,
            reference_tokens=10000,
        )
        assert cfg.reference_cost == 50.0
        assert cfg.reference_time_seconds == 600.0
        assert cfg.reference_tokens == 10000

    def test_reference_cost_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="greater than 0"):
            EfficiencyConfig(reference_cost=0.0)

    def test_reference_tokens_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="greater than 0"):
            EfficiencyConfig(reference_tokens=0)


class TestResilienceConfig:
    """ResilienceConfig tests."""

    def test_defaults(self) -> None:
        cfg = ResilienceConfig()
        assert cfg.success_rate_enabled is True
        assert cfg.recovery_rate_enabled is True
        assert cfg.consistency_enabled is True
        assert cfg.streak_enabled is True
        assert cfg.streak_factor == 1.0
        assert cfg.consistency_k == 2.0

    def test_weights_sum_close_to_one(self) -> None:
        cfg = ResilienceConfig()
        total = (
            cfg.success_rate_weight
            + cfg.recovery_rate_weight
            + cfg.consistency_weight
            + cfg.streak_weight
        )
        assert abs(total - 1.0) < 0.01


class TestGovernanceConfig:
    """GovernanceConfig tests."""

    def test_defaults(self) -> None:
        cfg = GovernanceConfig()
        assert cfg.audit_compliance_enabled is True
        assert cfg.trust_level_enabled is True
        assert cfg.autonomy_compliance_enabled is True

    def test_weights_sum_close_to_one(self) -> None:
        cfg = GovernanceConfig()
        total = (
            cfg.audit_compliance_weight
            + cfg.trust_level_weight
            + cfg.autonomy_compliance_weight
        )
        assert abs(total - 1.0) < 0.01


class TestExperienceConfig:
    """ExperienceConfig tests."""

    def test_defaults(self) -> None:
        cfg = ExperienceConfig()
        assert cfg.clarity_enabled is True
        assert cfg.tone_enabled is True
        assert cfg.helpfulness_enabled is True
        assert cfg.trust_enabled is True
        assert cfg.satisfaction_enabled is True
        assert cfg.min_feedback_count == 3

    def test_weights_sum_close_to_one(self) -> None:
        cfg = ExperienceConfig()
        total = (
            cfg.clarity_weight
            + cfg.tone_weight
            + cfg.helpfulness_weight
            + cfg.trust_weight
            + cfg.satisfaction_weight
        )
        assert abs(total - 1.0) < 0.01

    def test_min_feedback_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            ExperienceConfig(min_feedback_count=0)


class TestEvaluationConfig:
    """EvaluationConfig tests."""

    def test_defaults_all_pillars_enabled(self) -> None:
        cfg = EvaluationConfig()
        assert cfg.intelligence.enabled is True
        assert cfg.efficiency.enabled is True
        assert cfg.resilience.enabled is True
        assert cfg.governance.enabled is True
        assert cfg.experience.enabled is True
        assert cfg.calibration_drift_threshold == 2.0

    def test_frozen(self) -> None:
        cfg = EvaluationConfig()
        with pytest.raises(ValidationError):
            cfg.calibration_drift_threshold = 5.0  # type: ignore[misc]

    def test_single_pillar_enabled(self) -> None:
        """At least one pillar must be enabled -- single is fine."""
        cfg = EvaluationConfig(
            intelligence=IntelligenceConfig(enabled=True),
            efficiency=EfficiencyConfig(enabled=False),
            resilience=ResilienceConfig(enabled=False),
            governance=GovernanceConfig(enabled=False),
            experience=ExperienceConfig(enabled=False),
        )
        assert cfg.intelligence.enabled is True

    def test_all_pillars_disabled_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one evaluation pillar"):
            EvaluationConfig(
                intelligence=IntelligenceConfig(enabled=False),
                efficiency=EfficiencyConfig(enabled=False),
                resilience=ResilienceConfig(enabled=False),
                governance=GovernanceConfig(enabled=False),
                experience=ExperienceConfig(enabled=False),
            )

    def test_serialization_roundtrip(self) -> None:
        cfg = EvaluationConfig(
            intelligence=IntelligenceConfig(llm_calibration_enabled=False),
            efficiency=EfficiencyConfig(tokens_enabled=False),
        )
        data = cfg.model_dump()
        restored = EvaluationConfig.model_validate(data)
        assert restored.intelligence.llm_calibration_enabled is False
        assert restored.efficiency.tokens_enabled is False

    def test_calibration_drift_bounds(self) -> None:
        EvaluationConfig(calibration_drift_threshold=0.0)
        EvaluationConfig(calibration_drift_threshold=10.0)
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            EvaluationConfig(calibration_drift_threshold=-0.1)
        with pytest.raises(ValueError, match="less than or equal to 10"):
            EvaluationConfig(calibration_drift_threshold=10.1)

    @pytest.mark.parametrize(
        "pillar_field",
        ["intelligence", "efficiency", "resilience", "governance", "experience"],
    )
    def test_disable_individual_pillar(self, pillar_field: str) -> None:
        """Each pillar can be disabled independently."""
        configs = {
            "intelligence": IntelligenceConfig,
            "efficiency": EfficiencyConfig,
            "resilience": ResilienceConfig,
            "governance": GovernanceConfig,
            "experience": ExperienceConfig,
        }
        kwargs = {pillar_field: configs[pillar_field](enabled=False)}
        cfg = EvaluationConfig(**kwargs)
        assert getattr(cfg, pillar_field).enabled is False
        # All others still enabled.
        for other_field in configs:
            if other_field != pillar_field:
                assert getattr(cfg, other_field).enabled is True

    def test_pillar_enabled_all_metrics_disabled_raises(self) -> None:
        """Pillar enabled but all metrics disabled must raise."""
        with pytest.raises(ValueError, match="At least one metric"):
            IntelligenceConfig(
                enabled=True,
                ci_quality_enabled=False,
                llm_calibration_enabled=False,
            )

    def test_pillar_disabled_all_metrics_disabled_ok(self) -> None:
        """Pillar disabled with all metrics disabled is fine."""
        cfg = IntelligenceConfig(
            enabled=False,
            ci_quality_enabled=False,
            llm_calibration_enabled=False,
        )
        assert cfg.enabled is False

    @pytest.mark.parametrize(
        ("config_cls", "disable_kwargs"),
        [
            (
                EfficiencyConfig,
                {"cost_enabled": False, "time_enabled": False, "tokens_enabled": False},
            ),
            (
                ResilienceConfig,
                {
                    "success_rate_enabled": False,
                    "recovery_rate_enabled": False,
                    "consistency_enabled": False,
                    "streak_enabled": False,
                },
            ),
            (
                GovernanceConfig,
                {
                    "audit_compliance_enabled": False,
                    "trust_level_enabled": False,
                    "autonomy_compliance_enabled": False,
                },
            ),
            (
                ExperienceConfig,
                {
                    "clarity_enabled": False,
                    "tone_enabled": False,
                    "helpfulness_enabled": False,
                    "trust_enabled": False,
                    "satisfaction_enabled": False,
                },
            ),
        ],
    )
    def test_all_metrics_disabled_raises_per_config(
        self,
        config_cls: type,
        disable_kwargs: dict[str, bool],
    ) -> None:
        """Each pillar config raises when all metrics disabled."""
        with pytest.raises(ValueError, match="At least one metric"):
            config_cls(enabled=True, **disable_kwargs)
