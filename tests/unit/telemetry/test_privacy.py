"""Tests for the telemetry privacy scrubber."""

from datetime import UTC, datetime

import pytest

from synthorg.telemetry.privacy import PrivacyScrubber, PrivacyViolationError
from synthorg.telemetry.protocol import TelemetryEvent


def _make_event(
    event_type: str = "deployment.heartbeat",
    **properties: int | float | str | bool,
) -> TelemetryEvent:
    return TelemetryEvent(
        event_type=event_type,
        deployment_id="test-id",
        synthorg_version="0.6.4",
        python_version="3.14.0",
        os_platform="Linux",
        timestamp=datetime.now(UTC),
        properties=properties,
    )


@pytest.mark.unit
class TestPrivacyScrubber:
    """Privacy scrubber validation rules."""

    def setup_method(self) -> None:
        self.scrubber = PrivacyScrubber()

    def test_valid_heartbeat_passes(self) -> None:
        event = _make_event(
            "deployment.heartbeat",
            agent_count=5,
            department_count=3,
            team_count=2,
            template_name="startup",
            persistence_backend="sqlite",
            memory_backend="mem0",
            features_enabled="meeting,delegation",
            uptime_hours=12.5,
        )
        result = self.scrubber.validate(event)
        assert result is event

    def test_valid_session_summary_passes(self) -> None:
        event = _make_event(
            "deployment.session_summary",
            tasks_created=10,
            tasks_completed=8,
            tasks_failed=2,
            error_rate_limit=1,
            error_timeout=0,
            error_connection=0,
            error_internal=1,
            error_validation=0,
            error_other=0,
            provider_count=2,
            topology_hierarchical=3,
            topology_parallel=1,
            topology_sequential=0,
            topology_auto=5,
            meetings_held=2,
            delegations_executed=4,
            uptime_hours=24.0,
        )
        result = self.scrubber.validate(event)
        assert result is event

    def test_valid_startup_passes(self) -> None:
        event = _make_event(
            "deployment.startup",
            agent_count=3,
            department_count=2,
            template_name="enterprise",
            persistence_backend="postgresql",
            memory_backend="custom",
        )
        result = self.scrubber.validate(event)
        assert result is event

    def test_valid_shutdown_passes(self) -> None:
        event = _make_event(
            "deployment.shutdown",
            uptime_hours=48.0,
            graceful=True,
        )
        result = self.scrubber.validate(event)
        assert result is event

    def test_rejects_unknown_event_type(self) -> None:
        event = _make_event("user.logged_in")
        with pytest.raises(PrivacyViolationError, match="Disallowed event type"):
            self.scrubber.validate(event)

    def test_rejects_unknown_property_key(self) -> None:
        event = _make_event(
            "deployment.heartbeat",
            agent_count=5,
            unknown_field=42,
        )
        with pytest.raises(PrivacyViolationError, match="Disallowed property"):
            self.scrubber.validate(event)

    @pytest.mark.parametrize(
        "bad_key",
        [
            "api_key",
            "secret_value",
            "jwt_token",
            "user_password",
            "message_content",
            "task_description",
            "system_prompt",
            "bearer_credential",
            "auth_header",
        ],
    )
    def test_rejects_forbidden_key_patterns(
        self, bad_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even if somehow added to the allowlist, forbidden
        patterns are caught.
        """
        from types import MappingProxyType

        from synthorg.telemetry import privacy

        original = privacy._ALLOWED_PROPERTIES["deployment.heartbeat"]
        patched = dict(privacy._ALLOWED_PROPERTIES)
        patched["deployment.heartbeat"] = original | {bad_key}
        monkeypatch.setattr(privacy, "_ALLOWED_PROPERTIES", MappingProxyType(patched))
        event_with_bad = _make_event("deployment.heartbeat", **{bad_key: "value"})
        with pytest.raises(PrivacyViolationError, match="Forbidden pattern"):
            self.scrubber.validate(event_with_bad)

    def test_rejects_long_string_values(self) -> None:
        event = _make_event(
            "deployment.heartbeat",
            template_name="x" * 100,
        )
        with pytest.raises(PrivacyViolationError, match="exceeds"):
            self.scrubber.validate(event)

    def test_accepts_max_length_string(self) -> None:
        event = _make_event(
            "deployment.heartbeat",
            template_name="x" * 64,
        )
        result = self.scrubber.validate(event)
        assert result is event

    def test_empty_properties_passes(self) -> None:
        event = _make_event("deployment.heartbeat")
        result = self.scrubber.validate(event)
        assert result is event
