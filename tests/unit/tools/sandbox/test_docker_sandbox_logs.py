"""Tests for Docker sandbox log collection, shipping, and env injection."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from synthorg.observability.config import ContainerLogShippingConfig
from synthorg.observability.events.sandbox import (
    SANDBOX_CONTAINER_LOGS_SHIPPED,
)
from synthorg.tools.sandbox.docker_sandbox import DockerSandbox

pytestmark = pytest.mark.unit

_MODULE = "synthorg.tools.sandbox.docker_sandbox"


# ── Helpers ─────────────────────────────────────────────────────


def _make_sidecar_log_lines(*entries: dict[str, Any]) -> list[str]:
    """Build Docker log output lines from JSON dicts."""
    return [json.dumps(e) + "\n" for e in entries]


def _make_mock_container(
    *,
    log_stdout: list[str] | None = None,
) -> MagicMock:
    """Create a mock aiodocker container for log collection."""
    mock = MagicMock()
    mock.log = AsyncMock(return_value=log_stdout or [])
    return mock


# ── Sidecar Log Collection ──────────────────────────────────────


class TestCollectSidecarLogs:
    """Tests for DockerSandbox._collect_sidecar_logs()."""

    async def test_valid_json_lines_parsed(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        lines = _make_sidecar_log_lines(
            {"ts": "2026-04-14T00:00:00Z", "level": "info", "msg": "started"},
            {"ts": "2026-04-14T00:00:01Z", "level": "debug", "msg": "dns query"},
        )
        mock_container = _make_mock_container(log_stdout=lines)
        mock_docker = MagicMock()
        mock_docker.containers.container = MagicMock(
            return_value=mock_container,
        )

        config = ContainerLogShippingConfig()
        result = await sandbox._collect_sidecar_logs(
            mock_docker,
            "sidecar123",
            config=config,
        )

        assert len(result) == 2
        assert result[0]["msg"] == "started"
        assert result[1]["msg"] == "dns query"

    async def test_malformed_lines_skipped(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        lines = [
            '{"level": "info", "msg": "good"}\n',
            "not valid json\n",
            '{"level": "warn", "msg": "also good"}\n',
        ]
        mock_container = _make_mock_container(log_stdout=lines)
        mock_docker = MagicMock()
        mock_docker.containers.container = MagicMock(
            return_value=mock_container,
        )

        config = ContainerLogShippingConfig()
        result = await sandbox._collect_sidecar_logs(
            mock_docker,
            "sidecar123",
            config=config,
        )

        assert len(result) == 2
        assert result[0]["msg"] == "good"
        assert result[1]["msg"] == "also good"

    async def test_empty_logs_returns_empty_tuple(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        mock_container = _make_mock_container(log_stdout=[])
        mock_docker = MagicMock()
        mock_docker.containers.container = MagicMock(
            return_value=mock_container,
        )

        config = ContainerLogShippingConfig()
        result = await sandbox._collect_sidecar_logs(
            mock_docker,
            "sidecar123",
            config=config,
        )

        assert result == ()

    async def test_timeout_returns_empty_tuple(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        mock_container = _make_mock_container()
        mock_container.log = AsyncMock(side_effect=TimeoutError)
        mock_docker = MagicMock()
        mock_docker.containers.container = MagicMock(
            return_value=mock_container,
        )

        config = ContainerLogShippingConfig(collection_timeout_seconds=0.1)
        result = await sandbox._collect_sidecar_logs(
            mock_docker,
            "sidecar123",
            config=config,
        )

        assert result == ()

    async def test_exception_returns_empty_tuple(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        mock_container = _make_mock_container()
        mock_container.log = AsyncMock(
            side_effect=RuntimeError("docker gone"),
        )
        mock_docker = MagicMock()
        mock_docker.containers.container = MagicMock(
            return_value=mock_container,
        )

        config = ContainerLogShippingConfig()
        result = await sandbox._collect_sidecar_logs(
            mock_docker,
            "sidecar123",
            config=config,
        )

        assert result == ()

    async def test_max_log_bytes_truncation(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        # Each line is ~50 bytes JSON. Set max to 60 so only first fits.
        lines = _make_sidecar_log_lines(
            {"msg": "a" * 30},
            {"msg": "b" * 30},
            {"msg": "c" * 30},
        )
        mock_container = _make_mock_container(log_stdout=lines)
        mock_docker = MagicMock()
        mock_docker.containers.container = MagicMock(
            return_value=mock_container,
        )

        config = ContainerLogShippingConfig(max_log_bytes=60)
        result = await sandbox._collect_sidecar_logs(
            mock_docker,
            "sidecar123",
            config=config,
        )

        # Should stop collecting once cumulative bytes exceed max
        assert len(result) < 3


# ── Log Shipping ────────────────────────────────────────────────


class TestShipContainerLogs:
    """Tests for DockerSandbox._ship_container_logs()."""

    async def test_emits_shipped_event(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        config = ContainerLogShippingConfig()

        with structlog.testing.capture_logs() as cap:
            await sandbox._ship_container_logs(
                config=config,
                container_id="abc123def456",
                sidecar_id="side789",
                stdout="hello world",
                stderr="",
                sidecar_logs=({"msg": "sidecar event"},),
                execution_time_ms=1200,
            )

        shipped = [e for e in cap if e["event"] == SANDBOX_CONTAINER_LOGS_SHIPPED]
        assert len(shipped) == 1
        assert shipped[0]["container_id"] == "abc123def456"  # 12-char short ID
        assert shipped[0]["sidecar_id"] == "side789"
        assert shipped[0]["execution_time_ms"] == 1200

    async def test_disabled_config_skips_shipping(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        config = ContainerLogShippingConfig(enabled=False)

        with structlog.testing.capture_logs() as cap:
            await sandbox._ship_container_logs(
                config=config,
                container_id="abc123",
                sidecar_id=None,
                stdout="output",
                stderr="",
                sidecar_logs=(),
                execution_time_ms=100,
            )

        shipped = [e for e in cap if e["event"] == SANDBOX_CONTAINER_LOGS_SHIPPED]
        assert len(shipped) == 0

    async def test_shipping_failure_does_not_raise(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        config = ContainerLogShippingConfig()

        # Patch logger to raise on info call
        with patch(f"{_MODULE}.logger") as mock_logger:
            mock_logger.info.side_effect = RuntimeError("logging broken")
            mock_logger.debug = MagicMock()

            # Should not raise
            await sandbox._ship_container_logs(
                config=config,
                container_id="abc123",
                sidecar_id=None,
                stdout="output",
                stderr="",
                sidecar_logs=(),
                execution_time_ms=100,
            )

            # Failure logged at debug
            mock_logger.debug.assert_called_once()

    async def test_stdout_stderr_truncated_to_max_bytes(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        config = ContainerLogShippingConfig(max_log_bytes=100)

        with structlog.testing.capture_logs() as cap:
            await sandbox._ship_container_logs(
                config=config,
                container_id="abc123",
                sidecar_id=None,
                stdout="x" * 500,
                stderr="y" * 500,
                sidecar_logs=(),
                execution_time_ms=100,
            )

        shipped = [e for e in cap if e["event"] == SANDBOX_CONTAINER_LOGS_SHIPPED]
        assert len(shipped) == 1
        assert len(shipped[0]["stdout"]) <= 100
        assert len(shipped[0]["stderr"]) <= 100

    async def test_no_sidecar_id_handled(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        config = ContainerLogShippingConfig()

        with structlog.testing.capture_logs() as cap:
            await sandbox._ship_container_logs(
                config=config,
                container_id="abc123",
                sidecar_id=None,
                stdout="output",
                stderr="",
                sidecar_logs=(),
                execution_time_ms=50,
            )

        shipped = [e for e in cap if e["event"] == SANDBOX_CONTAINER_LOGS_SHIPPED]
        assert len(shipped) == 1
        assert shipped[0]["sidecar_id"] is None


# ── Correlation Env Injection ───────────────────────────────────


class TestCorrelationEnvInjection:
    """Tests for SYNTHORG_* env var injection from contextvars."""

    async def test_synthorg_vars_injected_from_contextvars(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]

        with patch(
            "structlog.contextvars.get_contextvars",
            return_value={
                "agent_id": "agent-ceo",
                "task_id": "task-42",
                "request_id": "req-abc",
            },
        ):
            env_list = sandbox._build_correlation_env()

        env_dict = dict(item.split("=", 1) for item in env_list)
        assert env_dict["SYNTHORG_AGENT_ID"] == "agent-ceo"
        assert env_dict["SYNTHORG_TASK_ID"] == "task-42"
        assert env_dict["SYNTHORG_REQUEST_ID"] == "req-abc"

    async def test_missing_contextvars_yield_empty_strings(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]

        with patch(
            "structlog.contextvars.get_contextvars",
            return_value={},
        ):
            env_list = sandbox._build_correlation_env()

        env_dict = dict(item.split("=", 1) for item in env_list)
        assert env_dict["SYNTHORG_AGENT_ID"] == ""
        assert env_dict["SYNTHORG_TASK_ID"] == ""
        assert env_dict["SYNTHORG_REQUEST_ID"] == ""

    def test_synthorg_prefix_not_blocked_by_reserved_keys(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        # Should not raise even though keys start with SYNTHORG_
        env_list = sandbox._validate_env(
            {"SYNTHORG_AGENT_ID": "agent-ceo", "MY_VAR": "val"},
        )
        env_dict = dict(item.split("=", 1) for item in env_list)
        assert "SYNTHORG_AGENT_ID" in env_dict
        assert "MY_VAR" in env_dict

    def test_reserved_sidecar_keys_still_blocked(
        self,
        tmp_path: object,
    ) -> None:
        from synthorg.tools.sandbox.errors import SandboxError

        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]
        with pytest.raises(SandboxError, match="reserved"):
            sandbox._validate_env(
                {"SIDECAR_ALLOWED_HOSTS": "evil"},
            )

    def test_user_env_merged_with_correlation_vars(
        self,
        tmp_path: object,
    ) -> None:
        sandbox = DockerSandbox(workspace=tmp_path)  # type: ignore[arg-type]

        with patch(
            "structlog.contextvars.get_contextvars",
            return_value={"agent_id": "agent-cto"},
        ):
            correlation_env = sandbox._build_correlation_env()

        user_env = sandbox._validate_env({"MY_VAR": "hello"})
        merged = user_env + correlation_env

        env_dict = dict(item.split("=", 1) for item in merged)
        assert env_dict["MY_VAR"] == "hello"
        assert env_dict["SYNTHORG_AGENT_ID"] == "agent-cto"


# ── Instance Config Fallback ───────────────────────────────────


class TestInstanceConfigFallback:
    """Methods fall back to self._log_shipping_config when no config passed."""

    async def test_collect_uses_instance_config(
        self,
        tmp_path: object,
    ) -> None:
        custom = ContainerLogShippingConfig(
            collection_timeout_seconds=0.5,
        )
        sandbox = DockerSandbox(
            workspace=tmp_path,  # type: ignore[arg-type]
            log_shipping_config=custom,
        )
        mock_container = _make_mock_container(
            log_stdout=['{"msg": "ok"}\n'],
        )
        mock_docker = MagicMock()
        mock_docker.containers.container = MagicMock(
            return_value=mock_container,
        )

        # Call WITHOUT explicit config= -- should use instance config.
        result = await sandbox._collect_sidecar_logs(
            mock_docker,
            "sidecar123",
        )
        assert len(result) == 1

    async def test_ship_uses_instance_config(
        self,
        tmp_path: object,
    ) -> None:
        custom = ContainerLogShippingConfig(enabled=False)
        sandbox = DockerSandbox(
            workspace=tmp_path,  # type: ignore[arg-type]
            log_shipping_config=custom,
        )

        with structlog.testing.capture_logs() as cap:
            # Call WITHOUT config= -- should use instance (disabled).
            await sandbox._ship_container_logs(
                container_id="abc123",
                sidecar_id=None,
                stdout="out",
                stderr="",
                sidecar_logs=(),
                execution_time_ms=50,
            )

        shipped = [e for e in cap if e["event"] == SANDBOX_CONTAINER_LOGS_SHIPPED]
        assert len(shipped) == 0  # disabled by instance config
