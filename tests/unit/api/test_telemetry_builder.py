"""Tests for the app-level telemetry collector factory.

``_build_telemetry_collector`` builds a :class:`TelemetryCollector`
wired against the memory-dir env var. The collector respects
``SYNTHORG_TELEMETRY`` internally; this module verifies the path
derivation, env-var handling, and memory-dir validation around
construction.
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


@pytest.mark.unit
class TestMemoryDirValidation:
    """Reject junk ``SYNTHORG_MEMORY_DIR`` values before deriving paths.

    ``memory_dir.parent / "telemetry"`` is only meaningful when the
    env var is an absolute container path; empty, whitespace-only,
    or relative values would land the deployment ID under
    ``/telemetry`` or a cwd-relative directory and silently miss
    the data volume. The builder falls back to ``/data/memory``
    (its default) in each of those cases so misconfiguration is
    observable via logs but does not poison persistence.
    """

    @pytest.mark.parametrize(
        "bad_value",
        [
            pytest.param("", id="empty_string"),
            pytest.param("   ", id="whitespace_only"),
            pytest.param("\t\n", id="tabs_and_newlines"),
            pytest.param("relative/path", id="relative_subdir"),
            pytest.param("./memory", id="dot_relative"),
            pytest.param("memory", id="bare_name"),
        ],
    )
    def test_invalid_values_fall_back_to_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
        bad_value: str,
    ) -> None:
        monkeypatch.setenv("SYNTHORG_MEMORY_DIR", bad_value)
        monkeypatch.delenv("SYNTHORG_TELEMETRY", raising=False)
        collector = _build_telemetry_collector()
        # Falls back to ``/data/memory`` -> ``/data/telemetry``.
        assert collector._data_dir == Path("/data/telemetry")

    def test_absolute_path_with_whitespace_is_trimmed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv(
            "SYNTHORG_MEMORY_DIR",
            f"  {tmp_path / 'memory'}  ",
        )
        monkeypatch.delenv("SYNTHORG_TELEMETRY", raising=False)
        collector = _build_telemetry_collector()
        # Surrounding whitespace is stripped before path resolution.
        assert collector._data_dir == tmp_path / "telemetry"
