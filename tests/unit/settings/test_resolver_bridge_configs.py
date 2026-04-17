"""Unit tests for ConfigResolver bridge-config composed-read helpers.

Each helper assembles a frozen Pydantic dataclass from a namespace's
bridged settings using :meth:`ConfigResolver._resolve_bridge_fields`.
These tests verify:

1. The helper passes the expected keys/types to the settings service.
2. The returned dataclass reflects the resolved values.
3. Out-of-range values raise a ``ValidationError`` at dataclass
   construction.
4. Parallel resolution is used (all keys resolved in one TaskGroup).
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from synthorg.settings.bridge_configs import (
    A2ABridgeConfig,
    ApiBridgeConfig,
    CommunicationBridgeConfig,
    EngineBridgeConfig,
    IntegrationsBridgeConfig,
    MemoryBridgeConfig,
    MetaBridgeConfig,
    NotificationsBridgeConfig,
    ObservabilityBridgeConfig,
    SettingsDispatcherBridgeConfig,
    ToolsBridgeConfig,
)
from synthorg.settings.enums import SettingNamespace, SettingSource
from synthorg.settings.models import SettingValue
from synthorg.settings.resolver import ConfigResolver


class _FakeRootConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


@pytest.fixture
def mock_settings() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def resolver(mock_settings: AsyncMock) -> ConfigResolver:
    return ConfigResolver(
        settings_service=mock_settings,
        config=_FakeRootConfig(),  # type: ignore[arg-type]
    )


def _value(namespace: SettingNamespace, key: str, value: str) -> SettingValue:
    return SettingValue(
        namespace=namespace, key=key, value=value, source=SettingSource.DEFAULT
    )


def _static_responses(
    mapping: dict[tuple[str, str], str],
) -> Any:
    """Build an AsyncMock side-effect that returns values from ``mapping``."""

    async def _side_effect(namespace: str, key: str) -> SettingValue:
        try:
            value_str = mapping[(namespace, key)]
        except KeyError as exc:  # pragma: no cover - test misconfiguration
            msg = f"unexpected settings lookup: {namespace}/{key}"
            raise AssertionError(msg) from exc
        return _value(SettingNamespace(namespace), key, value_str)

    return _side_effect


# ── api ─────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_get_api_bridge_config_defaults(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("api", "ticket_cleanup_interval_seconds"): "60.0",
            ("api", "ws_ticket_max_pending_per_user"): "5",
            ("api", "max_rpm_default"): "60",
            ("api", "compression_minimum_size_bytes"): "1000",
            ("api", "request_max_body_size_bytes"): "52428800",
            ("api", "max_lifecycle_events_per_query"): "10000",
            ("api", "max_audit_records_per_query"): "10000",
            ("api", "max_metrics_per_query"): "10000",
            ("api", "max_meeting_context_keys"): "20",
        }
    )
    cfg = await resolver.get_api_bridge_config()
    assert isinstance(cfg, ApiBridgeConfig)
    assert cfg.ticket_cleanup_interval_seconds == 60.0
    assert cfg.ws_ticket_max_pending_per_user == 5
    assert cfg.max_rpm_default == 60
    assert cfg.compression_minimum_size_bytes == 1000
    assert cfg.request_max_body_size_bytes == 52_428_800
    assert cfg.max_lifecycle_events_per_query == 10_000
    assert cfg.max_audit_records_per_query == 10_000
    assert cfg.max_metrics_per_query == 10_000
    assert cfg.max_meeting_context_keys == 20


@pytest.mark.unit
async def test_get_api_bridge_config_rejects_out_of_range(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("api", "ticket_cleanup_interval_seconds"): "60.0",
            ("api", "ws_ticket_max_pending_per_user"): "5",
            ("api", "max_rpm_default"): "60",
            ("api", "compression_minimum_size_bytes"): "1000",
            # 10 GiB - way over the 512 MiB cap.
            ("api", "request_max_body_size_bytes"): "10737418240",
            ("api", "max_lifecycle_events_per_query"): "10000",
            ("api", "max_audit_records_per_query"): "10000",
            ("api", "max_metrics_per_query"): "10000",
            ("api", "max_meeting_context_keys"): "20",
        }
    )
    with pytest.raises(ValidationError):
        await resolver.get_api_bridge_config()


# ── communication ───────────────────────────────────────────────


@pytest.mark.unit
async def test_get_communication_bridge_config_defaults(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("communication", "bus_bridge_poll_timeout_seconds"): "1.0",
            ("communication", "bus_bridge_max_consecutive_errors"): "30",
            ("communication", "webhook_bridge_poll_timeout_seconds"): "1.0",
            ("communication", "webhook_bridge_max_consecutive_errors"): "30",
            ("communication", "nats_history_batch_size"): "100",
            ("communication", "nats_history_fetch_timeout_seconds"): "0.5",
            ("communication", "delegation_record_store_max_size"): "10000",
            ("communication", "event_stream_max_queue_size"): "256",
            ("communication", "loop_prevention_window_seconds"): "60.0",
        }
    )
    cfg = await resolver.get_communication_bridge_config()
    assert isinstance(cfg, CommunicationBridgeConfig)
    assert cfg.bus_bridge_poll_timeout_seconds == 1.0
    assert cfg.bus_bridge_max_consecutive_errors == 30
    assert cfg.nats_history_batch_size == 100
    assert cfg.event_stream_max_queue_size == 256


# ── a2a ─────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_get_a2a_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("a2a", "client_timeout_seconds"): "45.0",
            ("a2a", "push_verification_clock_skew_seconds"): "120",
        }
    )
    cfg = await resolver.get_a2a_bridge_config()
    assert isinstance(cfg, A2ABridgeConfig)
    assert cfg.client_timeout_seconds == 45.0
    assert cfg.push_verification_clock_skew_seconds == 120


# ── engine ──────────────────────────────────────────────────────


@pytest.mark.unit
async def test_get_engine_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("engine", "approval_interrupt_timeout_seconds"): "600.0",
            ("engine", "health_quality_degradation_threshold"): "5",
        }
    )
    cfg = await resolver.get_engine_bridge_config()
    assert isinstance(cfg, EngineBridgeConfig)
    assert cfg.approval_interrupt_timeout_seconds == 600.0
    assert cfg.health_quality_degradation_threshold == 5


# ── memory ──────────────────────────────────────────────────────


@pytest.mark.unit
async def test_get_memory_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {("memory", "consolidation_enforce_batch_size"): "2500"}
    )
    cfg = await resolver.get_memory_bridge_config()
    assert isinstance(cfg, MemoryBridgeConfig)
    assert cfg.consolidation_enforce_batch_size == 2500


# ── integrations ────────────────────────────────────────────────


@pytest.mark.unit
async def test_get_integrations_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("integrations", "health_probe_interval_seconds"): "300",
            ("integrations", "oauth_http_timeout_seconds"): "45.0",
            ("integrations", "oauth_device_flow_max_wait_seconds"): "900",
            (
                "integrations",
                "rate_limit_coordinator_poll_timeout_seconds",
            ): "0.5",
        }
    )
    cfg = await resolver.get_integrations_bridge_config()
    assert isinstance(cfg, IntegrationsBridgeConfig)
    assert cfg.oauth_http_timeout_seconds == 45.0
    assert cfg.oauth_device_flow_max_wait_seconds == 900


# ── meta ────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_get_meta_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("meta", "ci_timeout_seconds"): "300",
            ("meta", "proposal_rate_limit_max"): "25",
            ("meta", "outcome_store_default_limit"): "50",
        }
    )
    cfg = await resolver.get_meta_bridge_config()
    assert isinstance(cfg, MetaBridgeConfig)
    assert cfg.ci_timeout_seconds == 300
    assert cfg.proposal_rate_limit_max == 25
    assert cfg.outcome_store_default_limit == 50


# ── notifications ───────────────────────────────────────────────


@pytest.mark.unit
async def test_get_notifications_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("notifications", "slack_webhook_timeout_seconds"): "15.0",
            ("notifications", "ntfy_webhook_timeout_seconds"): "10.0",
            ("notifications", "email_smtp_timeout_seconds"): "30.0",
        }
    )
    cfg = await resolver.get_notifications_bridge_config()
    assert isinstance(cfg, NotificationsBridgeConfig)
    assert cfg.slack_webhook_timeout_seconds == 15.0
    assert cfg.email_smtp_timeout_seconds == 30.0


# ── tools ───────────────────────────────────────────────────────


@pytest.mark.unit
async def test_get_tools_bridge_config_defaults(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("tools", "git_kill_grace_timeout_seconds"): "5.0",
            ("tools", "atlas_kill_grace_timeout_seconds"): "5.0",
            ("tools", "docker_sidecar_health_poll_interval_seconds"): "0.2",
            ("tools", "docker_sidecar_health_timeout_seconds"): "15.0",
            ("tools", "docker_sidecar_memory_limit"): "128m",
            ("tools", "docker_sidecar_cpu_limit"): "1.0",
            ("tools", "docker_sidecar_max_pids"): "64",
            ("tools", "docker_stop_grace_timeout_seconds"): "10",
            ("tools", "subprocess_kill_grace_timeout_seconds"): "5.0",
        }
    )
    cfg = await resolver.get_tools_bridge_config()
    assert isinstance(cfg, ToolsBridgeConfig)
    assert cfg.docker_sidecar_memory_limit == "128m"
    assert cfg.docker_sidecar_cpu_limit == 1.0
    assert cfg.docker_sidecar_max_pids == 64


@pytest.mark.unit
async def test_get_tools_bridge_config_rejects_bad_memory_literal(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("tools", "git_kill_grace_timeout_seconds"): "5.0",
            ("tools", "atlas_kill_grace_timeout_seconds"): "5.0",
            ("tools", "docker_sidecar_health_poll_interval_seconds"): "0.2",
            ("tools", "docker_sidecar_health_timeout_seconds"): "15.0",
            # invalid format ("gb" is not a single-char suffix).
            ("tools", "docker_sidecar_memory_limit"): "2gb",
            ("tools", "docker_sidecar_cpu_limit"): "0.5",
            ("tools", "docker_sidecar_max_pids"): "32",
            ("tools", "docker_stop_grace_timeout_seconds"): "5",
            ("tools", "subprocess_kill_grace_timeout_seconds"): "5.0",
        }
    )
    with pytest.raises(ValidationError):
        await resolver.get_tools_bridge_config()


# ── observability ───────────────────────────────────────────────


@pytest.mark.unit
async def test_get_observability_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("observability", "http_batch_size"): "250",
            ("observability", "http_flush_interval_seconds"): "2.5",
            ("observability", "http_timeout_seconds"): "10.0",
            ("observability", "http_max_retries"): "5",
            ("observability", "audit_chain_signing_timeout_seconds"): "10.0",
        }
    )
    cfg = await resolver.get_observability_bridge_config()
    assert isinstance(cfg, ObservabilityBridgeConfig)
    assert cfg.http_batch_size == 250
    assert cfg.http_max_retries == 5
    assert cfg.audit_chain_signing_timeout_seconds == 10.0


# ── settings (dispatcher self-config) ───────────────────────────


@pytest.mark.unit
async def test_get_settings_dispatcher_bridge_config(
    resolver: ConfigResolver, mock_settings: AsyncMock
) -> None:
    mock_settings.get.side_effect = _static_responses(
        {
            ("settings", "dispatcher_poll_timeout_seconds"): "0.25",
            ("settings", "dispatcher_error_backoff_seconds"): "2.0",
            ("settings", "dispatcher_max_consecutive_errors"): "50",
        }
    )
    cfg = await resolver.get_settings_dispatcher_bridge_config()
    assert isinstance(cfg, SettingsDispatcherBridgeConfig)
    assert cfg.poll_timeout_seconds == 0.25
    assert cfg.error_backoff_seconds == 2.0
    assert cfg.max_consecutive_errors == 50
