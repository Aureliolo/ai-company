"""Tests for the app-level telemetry collector factory.

``_build_telemetry_collector`` builds a :class:`TelemetryCollector`
wired against the memory-dir env var. The collector respects
``SYNTHORG_TELEMETRY`` internally; this module verifies the path
derivation and env-var handling around construction.
"""

from pathlib import Path

import pytest

from synthorg.api.app import _build_telemetry_collector
from synthorg.telemetry.collector import TelemetryCollector


@pytest.mark.unit
class TestBuildTelemetryCollector:
    """Env-var handling and data-dir derivation."""

    def test_defaults_to_container_path_when_env_unset(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("SYNTHORG_MEMORY_DIR", raising=False)
        monkeypatch.delenv("SYNTHORG_TELEMETRY", raising=False)
        collector = _build_telemetry_collector()
        assert isinstance(collector, TelemetryCollector)
        assert collector._data_dir == Path("/data/telemetry")
        assert collector.enabled is False

    def test_derives_sibling_dir_from_memory_dir(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        memory_dir = tmp_path / "memory"
        monkeypatch.setenv("SYNTHORG_MEMORY_DIR", str(memory_dir))
        monkeypatch.delenv("SYNTHORG_TELEMETRY", raising=False)
        collector = _build_telemetry_collector()
        assert collector._data_dir == tmp_path / "telemetry"

    def test_opt_in_flips_enabled_via_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("SYNTHORG_MEMORY_DIR", str(tmp_path / "memory"))
        monkeypatch.setenv("SYNTHORG_TELEMETRY", "true")
        collector = _build_telemetry_collector()
        assert collector.enabled is True
        # Deployment ID gets persisted under the derived telemetry dir.
        assert (tmp_path / "telemetry").exists()
