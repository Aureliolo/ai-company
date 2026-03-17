"""Shared fixtures and helpers for settings unit tests."""

from pydantic import BaseModel, ConfigDict

from synthorg.settings.enums import SettingNamespace, SettingSource
from synthorg.settings.models import SettingValue


def make_setting_value(
    value: str,
    namespace: SettingNamespace = SettingNamespace.BUDGET,
    key: str = "total_monthly",
) -> SettingValue:
    """Build a ``SettingValue`` for testing."""
    return SettingValue(
        namespace=namespace,
        key=key,
        value=value,
        source=SettingSource.DEFAULT,
    )


# ── Fake structural models ──────────────────────────────────────


class FakeAgentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = "agent-1"
    role: str = "developer"
    department: str = "eng"


class FakeDepartment(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = "eng"
    head: str = "lead"


class FakeProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    driver: str = "litellm"
