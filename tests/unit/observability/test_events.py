"""Tests for observability event name constants."""

import re

import pytest

from ai_company.observability import events

pytestmark = pytest.mark.timeout(30)

_DOT_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def _all_event_names() -> list[tuple[str, str]]:
    """Return (attr_name, value) for every public string constant in events."""
    result: list[tuple[str, str]] = []
    for attr in dir(events):
        if attr.startswith("_"):
            continue
        val = getattr(events, attr)
        if isinstance(val, str):
            result.append((attr, val))
    return result


@pytest.mark.unit
class TestEventConstants:
    def test_all_are_strings(self) -> None:
        for attr, val in _all_event_names():
            assert isinstance(val, str), f"{attr} is not a string"

    def test_follow_dot_pattern(self) -> None:
        for attr, val in _all_event_names():
            assert _DOT_PATTERN.match(val), (
                f"{attr}={val!r} does not match domain.noun.verb pattern"
            )

    def test_no_duplicates(self) -> None:
        values = [val for _, val in _all_event_names()]
        assert len(values) == len(set(values)), (
            f"Duplicate event names: {[v for v in values if values.count(v) > 1]}"
        )

    def test_has_at_least_20_events(self) -> None:
        assert len(_all_event_names()) >= 20

    def test_config_events_exist(self) -> None:
        assert events.CONFIG_LOADED == "config.load.success"
        assert events.CONFIG_PARSE_FAILED == "config.parse.failed"
        assert events.CONFIG_VALIDATION_FAILED == "config.validation.failed"

    def test_provider_events_exist(self) -> None:
        assert events.PROVIDER_CALL_START == "provider.call.start"
        assert events.PROVIDER_REGISTRY_BUILT == "provider.registry.built"

    def test_task_events_exist(self) -> None:
        assert events.TASK_STATUS_CHANGED == "task.status.changed"

    def test_template_events_exist(self) -> None:
        assert events.TEMPLATE_RENDER_START == "template.render.start"
        assert events.TEMPLATE_RENDER_SUCCESS == "template.render.success"

    def test_role_events_exist(self) -> None:
        assert events.ROLE_LOOKUP_MISS == "role.lookup.miss"
