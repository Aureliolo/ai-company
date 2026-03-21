"""Tests for meeting service auto-wiring."""

from unittest.mock import MagicMock

import pytest

from synthorg.communication.meeting.enums import MeetingProtocolType
from synthorg.communication.meeting.models import AgentResponse
from synthorg.communication.meeting.orchestrator import MeetingOrchestrator
from synthorg.communication.meeting.participant import (
    PassthroughParticipantResolver,
    RegistryParticipantResolver,
)
from synthorg.communication.meeting.scheduler import MeetingScheduler
from synthorg.config.schema import RootConfig

pytestmark = pytest.mark.timeout(30)


def _default_config() -> RootConfig:
    return RootConfig(company_name="test-company")


@pytest.mark.unit
class TestBuildProtocolRegistry:
    """Tests for _build_protocol_registry helper."""

    def test_returns_all_three_protocol_types(self) -> None:
        from synthorg.api.auto_wire import _build_protocol_registry

        registry = _build_protocol_registry()

        assert MeetingProtocolType.ROUND_ROBIN in registry
        assert MeetingProtocolType.POSITION_PAPERS in registry
        assert MeetingProtocolType.STRUCTURED_PHASES in registry
        assert len(registry) == 3

    def test_protocol_instances_report_correct_type(self) -> None:
        from synthorg.api.auto_wire import _build_protocol_registry

        registry = _build_protocol_registry()

        for proto_type, proto_impl in registry.items():
            assert proto_impl.get_protocol_type() == proto_type


@pytest.mark.unit
class TestStubAgentCaller:
    """Tests for _build_stub_agent_caller helper."""

    async def test_returns_valid_agent_response(self) -> None:
        from synthorg.api.auto_wire import _build_stub_agent_caller

        caller = _build_stub_agent_caller()
        response = await caller("agent-1", "test prompt", 100)

        assert isinstance(response, AgentResponse)
        assert response.agent_id == "agent-1"
        assert response.input_tokens == 0
        assert response.output_tokens == 0
        assert response.cost_usd == 0.0


@pytest.mark.unit
class TestWireMeetingOrchestrator:
    """Tests for _wire_meeting_orchestrator helper."""

    def test_creates_valid_orchestrator(self) -> None:
        from synthorg.api.auto_wire import _wire_meeting_orchestrator

        orchestrator = _wire_meeting_orchestrator()

        assert isinstance(orchestrator, MeetingOrchestrator)
        assert orchestrator.get_records() == ()


@pytest.mark.unit
class TestWireMeetingScheduler:
    """Tests for _wire_meeting_scheduler helper."""

    def test_uses_registry_resolver_when_available(self) -> None:
        from synthorg.api.auto_wire import (
            _wire_meeting_orchestrator,
            _wire_meeting_scheduler,
        )

        config = _default_config()
        orchestrator = _wire_meeting_orchestrator()
        registry = MagicMock()

        scheduler = _wire_meeting_scheduler(config, orchestrator, registry)

        assert isinstance(scheduler, MeetingScheduler)
        assert isinstance(scheduler._resolver, RegistryParticipantResolver)

    def test_uses_passthrough_resolver_when_no_registry(self) -> None:
        from synthorg.api.auto_wire import (
            _wire_meeting_orchestrator,
            _wire_meeting_scheduler,
        )

        config = _default_config()
        orchestrator = _wire_meeting_orchestrator()

        scheduler = _wire_meeting_scheduler(config, orchestrator, None)

        assert isinstance(scheduler, MeetingScheduler)
        assert isinstance(scheduler._resolver, PassthroughParticipantResolver)


@pytest.mark.unit
class TestAutoWireMeetings:
    """Tests for auto_wire_meetings main entry point."""

    def test_creates_both_services(self) -> None:
        from synthorg.api.auto_wire import auto_wire_meetings

        config = _default_config()
        result = auto_wire_meetings(
            effective_config=config,
            meeting_orchestrator=None,
            meeting_scheduler=None,
            agent_registry=None,
        )

        assert isinstance(result.meeting_orchestrator, MeetingOrchestrator)
        assert isinstance(result.meeting_scheduler, MeetingScheduler)

    def test_preserves_explicit_orchestrator(self) -> None:
        from synthorg.api.auto_wire import auto_wire_meetings

        config = _default_config()
        explicit_orch = MagicMock(spec=MeetingOrchestrator)

        result = auto_wire_meetings(
            effective_config=config,
            meeting_orchestrator=explicit_orch,
            meeting_scheduler=None,
            agent_registry=None,
        )

        assert result.meeting_orchestrator is explicit_orch
        assert isinstance(result.meeting_scheduler, MeetingScheduler)

    def test_preserves_explicit_scheduler(self) -> None:
        from synthorg.api.auto_wire import auto_wire_meetings

        config = _default_config()
        explicit_sched = MagicMock()

        result = auto_wire_meetings(
            effective_config=config,
            meeting_orchestrator=None,
            meeting_scheduler=explicit_sched,
            agent_registry=None,
        )

        assert isinstance(result.meeting_orchestrator, MeetingOrchestrator)
        assert result.meeting_scheduler is explicit_sched

    def test_preserves_both_explicit(self) -> None:
        from synthorg.api.auto_wire import auto_wire_meetings

        config = _default_config()
        explicit_orch = MagicMock(spec=MeetingOrchestrator)
        explicit_sched = MagicMock()

        result = auto_wire_meetings(
            effective_config=config,
            meeting_orchestrator=explicit_orch,
            meeting_scheduler=explicit_sched,
            agent_registry=None,
        )

        assert result.meeting_orchestrator is explicit_orch
        assert result.meeting_scheduler is explicit_sched

    def test_logs_auto_wire_events(self, capsys: pytest.CaptureFixture[str]) -> None:
        from synthorg.api.auto_wire import auto_wire_meetings

        config = _default_config()

        auto_wire_meetings(
            effective_config=config,
            meeting_orchestrator=None,
            meeting_scheduler=None,
            agent_registry=None,
        )

        captured = capsys.readouterr().out
        assert "meeting_orchestrator" in captured
        assert "meeting_scheduler" in captured
