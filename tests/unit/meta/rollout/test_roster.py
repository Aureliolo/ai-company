"""Tests for the OrgRoster protocol and default CallableOrgRoster."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.meta.rollout.roster import (
    CallableOrgRoster,
    NoOpOrgRoster,
    OrgRoster,
)

pytestmark = pytest.mark.unit


class TestNoOpRoster:
    async def test_returns_empty_tuple(self) -> None:
        assert await NoOpOrgRoster().list_agent_ids() == ()

    async def test_is_a_roster(self) -> None:
        assert isinstance(NoOpOrgRoster(), OrgRoster)


class TestCallableRoster:
    async def test_delegates_to_callable(self) -> None:
        async def source() -> tuple[NotBlankStr, ...]:
            return (
                NotBlankStr("agent-alpha"),
                NotBlankStr("agent-beta"),
            )

        roster = CallableOrgRoster(source)
        result = await roster.list_agent_ids()
        assert result == (
            NotBlankStr("agent-alpha"),
            NotBlankStr("agent-beta"),
        )

    async def test_reflects_live_state(self) -> None:
        agents: list[str] = []

        async def source() -> tuple[NotBlankStr, ...]:
            return tuple(NotBlankStr(a) for a in agents)

        roster = CallableOrgRoster(source)
        agents.append("agent-1")
        assert await roster.list_agent_ids() == (NotBlankStr("agent-1"),)
        agents.append("agent-2")
        assert await roster.list_agent_ids() == (
            NotBlankStr("agent-1"),
            NotBlankStr("agent-2"),
        )

    async def test_satisfies_protocol(self) -> None:
        async def source() -> tuple[NotBlankStr, ...]:
            return ()

        assert isinstance(CallableOrgRoster(source), OrgRoster)
