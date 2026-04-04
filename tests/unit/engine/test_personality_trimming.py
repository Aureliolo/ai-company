"""Unit tests for token-based personality trimming."""

from datetime import date

import pytest
import structlog.testing

from synthorg.core.agent import AgentIdentity, ModelConfig, PersonalityConfig
from synthorg.core.enums import (
    CollaborationPreference,
    CommunicationVerbosity,
    ConflictApproach,
    CreativityLevel,
    DecisionMakingStyle,
    RiskTolerance,
    SeniorityLevel,
)
from synthorg.engine._prompt_helpers import (
    _estimate_personality_tokens,
    _trim_personality,
    build_core_context,
)
from synthorg.engine.prompt import PersonalityTrimInfo, build_system_prompt
from synthorg.engine.prompt_profiles import PromptProfile, get_prompt_profile
from synthorg.engine.token_estimation import DefaultTokenEstimator
from synthorg.observability.events.prompt import PROMPT_PERSONALITY_TRIMMED


def _make_profile(
    *,
    tier: str = "large",
    max_tokens: int = 500,
    personality_mode: str = "full",
) -> PromptProfile:
    """Create a PromptProfile with custom max_personality_tokens."""
    return PromptProfile(
        tier=tier,  # type: ignore[arg-type]
        max_personality_tokens=max_tokens,
        personality_mode=personality_mode,  # type: ignore[arg-type]
    )


def _make_agent(
    *,
    description: str = "A precise thinker.",
    communication_style: str = "concise",
    traits: tuple[str, ...] = ("analytical",),
) -> AgentIdentity:
    """Create an agent with configurable personality fields."""
    return AgentIdentity(
        name="Test Agent",
        role="Developer",
        department="Engineering",
        level=SeniorityLevel.MID,
        model=ModelConfig(provider="test-provider", model_id="test-001"),
        hiring_date=date(2026, 1, 1),
        personality=PersonalityConfig(
            description=description,
            communication_style=communication_style,
            traits=traits,
            risk_tolerance=RiskTolerance.LOW,
            creativity=CreativityLevel.HIGH,
            verbosity=CommunicationVerbosity.VERBOSE,
            decision_making=DecisionMakingStyle.ANALYTICAL,
            collaboration=CollaborationPreference.TEAM,
            conflict_approach=ConflictApproach.COLLABORATE,
        ),
    )


def _verbose_agent() -> AgentIdentity:
    """Create an agent with a personality description at the 500-char limit."""
    # PersonalityConfig.description has max_length=500.
    long_desc = ("This agent is extremely verbose and detailed. " * 11)[:500]
    return _make_agent(
        description=long_desc.rstrip(),
        communication_style="extremely detailed and thorough",
        traits=(
            "analytical",
            "methodical",
            "detail-oriented",
            "perfectionist",
            "systematic",
        ),
    )


def _build_ctx(
    agent: AgentIdentity,
    profile: PromptProfile,
) -> dict[str, object]:
    """Build context dict with trimming disabled (for manual trimming tests)."""
    ctx, _ = build_core_context(
        agent,
        role=None,
        profile=profile,
        trimming_enabled=False,
    )
    return ctx


# ── TestEstimatePersonalityTokens ──────────────────────────────


@pytest.mark.unit
class TestEstimatePersonalityTokens:
    """Tests for personality section token estimation."""

    def test_full_mode_includes_all_fields(self) -> None:
        """Full mode estimate includes description, style, enums, traits."""
        agent = _make_agent()
        ctx = _build_ctx(agent, _make_profile(max_tokens=10000))
        estimator = DefaultTokenEstimator()

        tokens = _estimate_personality_tokens(ctx, "full", estimator)

        assert tokens > 0

    def test_condensed_mode_excludes_enums(self) -> None:
        """Condensed mode estimate is smaller than full mode."""
        agent = _make_agent()
        ctx = _build_ctx(agent, _make_profile(max_tokens=10000))
        estimator = DefaultTokenEstimator()

        full_tokens = _estimate_personality_tokens(ctx, "full", estimator)
        condensed_tokens = _estimate_personality_tokens(
            ctx,
            "condensed",
            estimator,
        )

        assert condensed_tokens < full_tokens

    def test_minimal_mode_smallest(self) -> None:
        """Minimal mode estimate is smallest of all modes."""
        agent = _make_agent()
        ctx = _build_ctx(agent, _make_profile(max_tokens=10000))
        estimator = DefaultTokenEstimator()

        condensed = _estimate_personality_tokens(ctx, "condensed", estimator)
        minimal = _estimate_personality_tokens(ctx, "minimal", estimator)

        assert minimal < condensed

    def test_empty_description_reduces_estimate(self) -> None:
        """Empty description produces fewer tokens than non-empty."""
        agent_with = _make_agent(description="A detailed description here.")
        agent_without = _make_agent(description="")
        estimator = DefaultTokenEstimator()

        ctx_with = _build_ctx(agent_with, _make_profile(max_tokens=10000))
        ctx_without = _build_ctx(agent_without, _make_profile(max_tokens=10000))

        tokens_with = _estimate_personality_tokens(ctx_with, "full", estimator)
        tokens_without = _estimate_personality_tokens(
            ctx_without,
            "full",
            estimator,
        )

        assert tokens_without < tokens_with


# ── TestTrimPersonality ────────────────────────────────────────


@pytest.mark.unit
class TestTrimPersonality:
    """Tests for progressive personality trimming."""

    def test_within_budget_no_trimming(self) -> None:
        """Personality within budget is not modified."""
        agent = _make_agent()
        profile = _make_profile(max_tokens=10000, personality_mode="full")
        ctx = _build_ctx(agent, profile)

        original_mode = ctx["personality_mode"]
        original_desc = ctx["personality_description"]

        result = _trim_personality(ctx, profile)

        assert result is None
        assert ctx["personality_mode"] == original_mode
        assert ctx["personality_description"] == original_desc

    def test_full_mode_over_budget_drops_to_condensed(self) -> None:
        """Full mode exceeding budget drops enums (becomes condensed)."""
        agent = _verbose_agent()
        estimator = DefaultTokenEstimator()
        # Probe to find a budget between full and condensed.
        ctx_probe = _build_ctx(agent, _make_profile(max_tokens=10000))
        full_tokens = _estimate_personality_tokens(
            ctx_probe,
            "full",
            estimator,
        )
        condensed_tokens = _estimate_personality_tokens(
            ctx_probe,
            "condensed",
            estimator,
        )
        budget = (full_tokens + condensed_tokens) // 2

        profile = _make_profile(max_tokens=budget, personality_mode="full")
        ctx = _build_ctx(agent, profile)
        result = _trim_personality(ctx, profile)

        assert result is not None
        assert result.trim_tier == 1
        assert ctx["personality_mode"] == "condensed"

    def test_condensed_over_budget_truncates_description(self) -> None:
        """Condensed mode over budget truncates description."""
        agent = _verbose_agent()
        original_desc = agent.personality.description

        profile = _make_profile(max_tokens=60, personality_mode="condensed")
        ctx = _build_ctx(agent, profile)
        result = _trim_personality(ctx, profile)

        assert result is not None
        assert result.trim_tier >= 2
        trimmed_desc = ctx["personality_description"]
        assert len(str(trimmed_desc)) < len(original_desc)
        if trimmed_desc:
            assert str(trimmed_desc).endswith("...")

    def test_severe_over_budget_falls_back_to_minimal(self) -> None:
        """Severely over budget falls back to minimal mode."""
        agent = _verbose_agent()
        profile = _make_profile(max_tokens=5, personality_mode="full")
        ctx = _build_ctx(agent, profile)
        result = _trim_personality(ctx, profile)

        assert result is not None
        assert result.trim_tier == 3
        assert ctx["personality_mode"] == "minimal"

    def test_already_minimal_within_budget(self) -> None:
        """Minimal mode within budget is not modified."""
        agent = _make_agent(description="", communication_style="concise")
        profile = _make_profile(max_tokens=10000, personality_mode="minimal")
        ctx = _build_ctx(agent, profile)
        result = _trim_personality(ctx, profile)

        assert result is None
        assert ctx["personality_mode"] == "minimal"
        assert ctx["communication_style"] == "concise"

    def test_description_truncation_at_word_boundary(self) -> None:
        """Truncation does not split mid-word."""
        agent = _make_agent(
            description="The quick brown fox jumps over the lazy dog repeatedly",
        )
        profile = _make_profile(max_tokens=15, personality_mode="condensed")
        ctx = _build_ctx(agent, profile)
        result = _trim_personality(ctx, profile)

        assert result is not None
        desc = str(ctx["personality_description"])
        if desc and desc != agent.personality.description:
            assert desc.endswith("...")
            without_ellipsis = desc[:-3].rstrip()
            # Should not end with a space (word boundary respected).
            assert without_ellipsis == "" or without_ellipsis[-1] != " "

    def test_empty_description_skips_to_minimal(self) -> None:
        """With no description, truncation tier is skipped."""
        agent = _make_agent(description="")
        profile = _make_profile(max_tokens=3, personality_mode="full")
        ctx = _build_ctx(agent, profile)
        result = _trim_personality(ctx, profile)

        assert result is not None
        assert ctx["personality_mode"] == "minimal"

    def test_trim_info_has_valid_fields(self) -> None:
        """PersonalityTrimInfo has correct before/after/max/tier."""
        agent = _verbose_agent()
        profile = _make_profile(max_tokens=50, personality_mode="full")
        ctx = _build_ctx(agent, profile)
        result = _trim_personality(ctx, profile)

        assert result is not None
        assert isinstance(result, PersonalityTrimInfo)
        assert result.before_tokens > result.max_tokens
        assert result.after_tokens <= result.max_tokens
        assert 1 <= result.trim_tier <= 3


# ── TestTrimPersonalityLogging ─────────────────────────────────


@pytest.mark.unit
class TestTrimPersonalityLogging:
    """Tests for personality trimming log events."""

    def test_trimming_logs_event(self) -> None:
        """Trimming logs PROMPT_PERSONALITY_TRIMMED with correct kwargs."""
        agent = _verbose_agent()
        profile = _make_profile(max_tokens=5, personality_mode="full")
        ctx = _build_ctx(agent, profile)

        with structlog.testing.capture_logs() as logs:
            _trim_personality(ctx, profile)

        trim_events = [e for e in logs if e["event"] == PROMPT_PERSONALITY_TRIMMED]
        assert len(trim_events) == 1
        entry = trim_events[0]
        assert "before_tokens" in entry
        assert "after_tokens" in entry
        assert "max_tokens" in entry
        assert "trim_tier" in entry
        assert entry["after_tokens"] <= entry["before_tokens"]

    def test_no_log_when_within_budget(self) -> None:
        """No trim event when personality is within budget."""
        agent = _make_agent()
        profile = _make_profile(max_tokens=10000, personality_mode="full")
        ctx = _build_ctx(agent, profile)

        with structlog.testing.capture_logs() as logs:
            _trim_personality(ctx, profile)

        trim_events = [e for e in logs if e["event"] == PROMPT_PERSONALITY_TRIMMED]
        assert len(trim_events) == 0


# ── TestTierLimits ─────────────────────────────────────────────


@pytest.mark.unit
class TestTierLimits:
    """Tests for trimming at each tier's default token limit."""

    def test_small_tier_80_token_cap(self) -> None:
        """Small tier (80 tokens) trims verbose personality."""
        agent = _verbose_agent()
        profile = get_prompt_profile("small")
        # build_core_context with trimming enabled enforces the cap.
        ctx, _ = build_core_context(
            agent,
            role=None,
            profile=profile,
        )
        estimator = DefaultTokenEstimator()

        tokens = _estimate_personality_tokens(
            ctx,
            ctx["personality_mode"],
            estimator,
        )

        assert tokens <= profile.max_personality_tokens

    def test_medium_tier_200_token_cap(self) -> None:
        """Medium tier (200 tokens) trims verbose personality."""
        agent = _verbose_agent()
        profile = get_prompt_profile("medium")
        ctx, _ = build_core_context(agent, role=None, profile=profile)
        estimator = DefaultTokenEstimator()

        tokens = _estimate_personality_tokens(
            ctx,
            ctx["personality_mode"],
            estimator,
        )

        assert tokens <= profile.max_personality_tokens

    def test_large_tier_500_token_cap(self) -> None:
        """Large tier (500 tokens) trims verbose personality."""
        agent = _verbose_agent()
        profile = get_prompt_profile("large")
        ctx, _ = build_core_context(agent, role=None, profile=profile)
        estimator = DefaultTokenEstimator()

        tokens = _estimate_personality_tokens(
            ctx,
            ctx["personality_mode"],
            estimator,
        )

        assert tokens <= profile.max_personality_tokens


# ── TestBuildSystemPromptIntegration ───────────────────────────


@pytest.mark.unit
class TestBuildSystemPromptIntegration:
    """End-to-end tests via build_system_prompt."""

    def test_small_tier_verbose_personality_trimmed(self) -> None:
        """build_system_prompt with small tier respects token cap."""
        agent = _verbose_agent()
        result = build_system_prompt(agent=agent, model_tier="small")

        # Personality enums should not appear (minimal mode).
        assert "Risk tolerance" not in result.content
        assert "Creativity" not in result.content
        assert "Verbosity" not in result.content

    def test_large_tier_normal_personality_untouched(self) -> None:
        """build_system_prompt with large tier and normal personality is full."""
        agent = _make_agent()
        result = build_system_prompt(agent=agent, model_tier="large")

        assert agent.personality.communication_style in result.content
        assert agent.personality.risk_tolerance.value in result.content
        assert agent.personality.creativity.value in result.content
        assert result.personality_trim_info is None

    def test_trimmed_prompt_still_valid(self) -> None:
        """Trimmed prompt is still a valid, non-empty SystemPrompt."""
        agent = _verbose_agent()
        result = build_system_prompt(agent=agent, model_tier="small")

        assert result.content.strip()
        assert result.estimated_tokens > 0
        assert "personality" in result.sections
        assert "identity" in result.sections

    def test_trim_info_populated_on_system_prompt(self) -> None:
        """PersonalityTrimInfo is set on SystemPrompt when trimming occurs."""
        agent = _verbose_agent()
        # Large profile has full mode with 500-char description, but
        # override to a very low token limit to force trimming.
        result = build_system_prompt(
            agent=agent,
            model_tier="large",
            max_personality_tokens_override=10,
        )

        assert result.personality_trim_info is not None
        assert result.personality_trim_info.before_tokens > 0
        assert result.personality_trim_info.trim_tier >= 1

    def test_trimming_disabled_bypasses_trimming(self) -> None:
        """personality_trimming_enabled=False skips trimming entirely."""
        agent = _verbose_agent()
        result = build_system_prompt(
            agent=agent,
            model_tier="small",
            personality_trimming_enabled=False,
        )

        assert result.personality_trim_info is None

    def test_max_personality_tokens_override(self) -> None:
        """max_personality_tokens_override overrides profile default."""
        agent = _verbose_agent()
        # Large profile normally allows 500 tokens. Override to 50.
        result = build_system_prompt(
            agent=agent,
            model_tier="large",
            max_personality_tokens_override=50,
        )

        assert result.personality_trim_info is not None
        assert result.personality_trim_info.max_tokens == 50

    def test_override_zero_uses_profile_default(self) -> None:
        """max_personality_tokens_override=0 is ignored (uses profile)."""
        agent = _make_agent()
        result = build_system_prompt(
            agent=agent,
            model_tier="large",
            max_personality_tokens_override=0,
        )

        # Normal personality fits in 500 tokens, no trimming.
        assert result.personality_trim_info is None
