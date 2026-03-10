"""Unit tests for org policy quality validation heuristics."""

import pytest
import structlog.testing

from ai_company.engine.policy_validation import (
    PolicyQualityIssue,
    validate_policy_quality,
)
from ai_company.observability.events.prompt import PROMPT_POLICY_QUALITY_ISSUE

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]


class TestPolicyQualityIssueModel:
    """Tests for the PolicyQualityIssue frozen model."""

    def test_valid_construction(self) -> None:
        issue = PolicyQualityIssue(
            policy="some policy",
            issue="some issue",
            severity="warning",
        )
        assert issue.policy == "some policy"
        assert issue.severity == "warning"

    def test_error_severity(self) -> None:
        issue = PolicyQualityIssue(
            policy="p",
            issue="i",
            severity="error",
        )
        assert issue.severity == "error"


class TestGoodPolicies:
    """Good policies should produce no issues."""

    @pytest.mark.parametrize(
        "policy",
        [
            "All API responses must include a correlation_id header",
            "Never store PII in memory without encryption",
            "Escalate budget overruns above $5 to the CFO",
            "Always validate user input before processing",
            "Agents should prefer structured logging over print statements",
        ],
    )
    def test_good_policy_no_issues(self, policy: str) -> None:
        result = validate_policy_quality((policy,))
        assert result == ()


class TestTooShort:
    """Policies shorter than 10 chars should produce a warning."""

    @pytest.mark.parametrize("policy", ["x", "ab", "short"])
    def test_too_short_warning(self, policy: str) -> None:
        result = validate_policy_quality((policy,))
        assert len(result) >= 1
        short_issues = [i for i in result if "Too short" in i.issue]
        assert len(short_issues) == 1
        assert short_issues[0].severity == "warning"


class TestTooLong:
    """Policies longer than 500 chars should produce a warning."""

    def test_too_long_warning(self) -> None:
        long_policy = "Agents must always " + "x" * 500
        result = validate_policy_quality((long_policy,))
        long_issues = [i for i in result if "Too long" in i.issue]
        assert len(long_issues) == 1
        assert long_issues[0].severity == "warning"


class TestCodePatterns:
    """Policies containing code patterns should produce a warning."""

    @pytest.mark.parametrize(
        "policy",
        [
            "The file src/api/controllers.py contains endpoints",
            "You should from os import path for file handling",
            "Use import json to parse data",
            "The def calculate_total(items) function handles pricing",
            "The class UserService: handles authentication",
        ],
    )
    def test_code_pattern_warning(self, policy: str) -> None:
        result = validate_policy_quality((policy,))
        code_issues = [i for i in result if "code patterns" in i.issue]
        assert len(code_issues) == 1
        assert code_issues[0].severity == "warning"


class TestMissingActionVerbs:
    """Policies without action verbs should produce a warning."""

    @pytest.mark.parametrize(
        "policy",
        [
            "The project uses Python 3.14 for all services",
            "Our database is PostgreSQL with replication",
            "The codebase follows a hexagonal architecture pattern",
        ],
    )
    def test_missing_action_verb_warning(self, policy: str) -> None:
        result = validate_policy_quality((policy,))
        verb_issues = [i for i in result if "action verbs" in i.issue]
        assert len(verb_issues) == 1
        assert verb_issues[0].severity == "warning"


class TestEdgeCases:
    """Edge cases for policy validation."""

    def test_empty_tuple_returns_empty(self) -> None:
        result = validate_policy_quality(())
        assert result == ()

    def test_single_char_produces_two_issues(self) -> None:
        """Single char is too short AND missing action verbs."""
        result = validate_policy_quality(("x",))
        assert len(result) >= 2

    def test_multiple_policies(self) -> None:
        """Validates all policies independently."""
        policies = (
            "All API responses must include correlation_id",
            "x",
        )
        result = validate_policy_quality(policies)
        # First is good, second produces issues.
        bad_issues = [i for i in result if i.policy == "x"]
        assert len(bad_issues) >= 1

    def test_logging_emits_events(self) -> None:
        """Each issue logs a PROMPT_POLICY_QUALITY_ISSUE event."""
        with structlog.testing.capture_logs() as logs:
            validate_policy_quality(("x",))

        events = [e for e in logs if e["event"] == PROMPT_POLICY_QUALITY_ISSUE]
        assert len(events) >= 1

    def test_multiple_code_patterns_produce_one_issue(self) -> None:
        """A policy with multiple code patterns produces exactly one issue."""
        policy = (
            "The file src/api/views.py has from os import path "
            "and also import json for parsing"
        )
        result = validate_policy_quality((policy,))
        code_issues = [i for i in result if "code patterns" in i.issue]
        assert len(code_issues) == 1

    def test_action_verb_word_boundary(self) -> None:
        """Noun forms of action verbs (e.g. 'requirement') don't match."""
        policy = (
            "The database has a strict isolation requirement and a validation framework"
        )
        result = validate_policy_quality((policy,))
        verb_issues = [i for i in result if "action verbs" in i.issue]
        assert len(verb_issues) == 1
