"""Tests for verification pluggable protocols, factory, and catalog."""

import pytest
from pydantic import ValidationError

from synthorg.engine.quality.decomposer_protocol import CriteriaDecomposer
from synthorg.engine.quality.decomposers.identity import (
    IdentityCriteriaDecomposer,
)
from synthorg.engine.quality.decomposers.llm import LLMCriteriaDecomposer
from synthorg.engine.quality.grader_protocol import RubricGrader
from synthorg.engine.quality.graders.heuristic import (
    HeuristicRubricGrader,
)
from synthorg.engine.quality.graders.llm import LLMRubricGrader
from synthorg.engine.quality.rubric_catalog import (
    BUILTIN_RUBRICS,
    get_rubric,
)
from synthorg.engine.quality.verification_config import (
    DecomposerVariant,
    GraderVariant,
    VerificationConfig,
)
from synthorg.engine.quality.verification_factory import (
    build_decomposer,
    build_grader,
)

# ── Protocol conformance ────────────────────────────────────────


@pytest.mark.unit
class TestProtocolConformance:
    def test_identity_decomposer_is_criteria_decomposer(self) -> None:
        assert isinstance(IdentityCriteriaDecomposer(), CriteriaDecomposer)

    def test_llm_decomposer_is_criteria_decomposer(self) -> None:
        assert isinstance(LLMCriteriaDecomposer(), CriteriaDecomposer)

    def test_heuristic_grader_is_rubric_grader(self) -> None:
        assert isinstance(HeuristicRubricGrader(), RubricGrader)

    def test_llm_grader_is_rubric_grader(self) -> None:
        assert isinstance(LLMRubricGrader(), RubricGrader)


# ── Factory ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestFactory:
    def test_build_identity_decomposer(self) -> None:
        cfg = VerificationConfig(decomposer=DecomposerVariant.IDENTITY)
        d = build_decomposer(cfg)
        assert isinstance(d, IdentityCriteriaDecomposer)
        assert d.name == "identity"

    def test_build_llm_decomposer_rejected(self) -> None:
        cfg = VerificationConfig(decomposer=DecomposerVariant.LLM)
        with pytest.raises(ValueError, match="Unknown decomposer"):
            build_decomposer(cfg)

    def test_build_heuristic_grader(self) -> None:
        cfg = VerificationConfig(grader=GraderVariant.HEURISTIC)
        g = build_grader(cfg)
        assert isinstance(g, HeuristicRubricGrader)
        assert g.name == "heuristic"

    def test_build_llm_grader_rejected(self) -> None:
        cfg = VerificationConfig(grader=GraderVariant.LLM)
        with pytest.raises(ValueError, match="Unknown grader"):
            build_grader(cfg)

    def test_each_build_produces_fresh_instance(self) -> None:
        cfg = VerificationConfig(decomposer=DecomposerVariant.IDENTITY)
        d1 = build_decomposer(cfg)
        d2 = build_decomposer(cfg)
        assert d1 is not d2


# ── Config ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestVerificationConfig:
    def test_default_config(self) -> None:
        cfg = VerificationConfig()
        assert cfg.decomposer == DecomposerVariant.IDENTITY
        assert cfg.grader == GraderVariant.HEURISTIC
        assert cfg.decomposer_model_tier == "medium"
        assert cfg.grader_model_tier == "medium"

    def test_frozen(self) -> None:
        cfg = VerificationConfig()
        with pytest.raises(ValidationError, match="frozen"):
            cfg.decomposer = DecomposerVariant.IDENTITY  # type: ignore[misc]

    def test_roundtrip(self) -> None:
        cfg = VerificationConfig(
            decomposer=DecomposerVariant.IDENTITY,
            grader=GraderVariant.HEURISTIC,
            max_probes_per_criterion=10,
        )
        restored = VerificationConfig.model_validate(cfg.model_dump())
        assert restored == cfg


# ── Rubric catalog ──────────────────────────────────────────────


@pytest.mark.unit
class TestRubricCatalog:
    def test_frontend_design_rubric_exists(self) -> None:
        rubric = get_rubric("frontend-design")
        assert rubric.name == "frontend-design"
        assert len(rubric.criteria) == 4

    def test_default_task_rubric_exists(self) -> None:
        rubric = get_rubric("default-task")
        assert rubric.name == "default-task"
        assert len(rubric.criteria) == 3

    def test_unknown_rubric_raises(self) -> None:
        with pytest.raises(KeyError, match="nonexistent"):
            get_rubric("nonexistent")

    def test_catalog_is_immutable(self) -> None:
        with pytest.raises(TypeError):
            BUILTIN_RUBRICS["new"] = None  # type: ignore[index]


@pytest.mark.unit
class TestFactoryErrorPaths:
    def test_unknown_decomposer_variant_raises(self) -> None:
        cfg = VerificationConfig(decomposer=DecomposerVariant.IDENTITY)
        valid_cfg = cfg.model_copy(
            update={"decomposer": "nonexistent"},
        )
        with pytest.raises(ValueError, match="Unknown decomposer"):
            build_decomposer(valid_cfg)

    def test_unknown_grader_variant_raises(self) -> None:
        cfg = VerificationConfig(grader=GraderVariant.HEURISTIC)
        valid_cfg = cfg.model_copy(
            update={"grader": "nonexistent"},
        )
        with pytest.raises(ValueError, match="Unknown grader"):
            build_grader(valid_cfg)
