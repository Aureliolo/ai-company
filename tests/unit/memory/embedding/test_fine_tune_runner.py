"""Tests for fine-tune pipeline container entrypoint."""

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synthorg.memory.embedding.fine_tune_runner import _load_config, _run

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _mock_health_server() -> Iterator[None]:
    """Prevent real port binding in tests."""
    mock_server = MagicMock()
    with patch(
        "synthorg.memory.embedding.fine_tune_runner._start_health_server",
        return_value=mock_server,
    ):
        yield


class TestLoadConfig:
    """Config file loading and validation."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            tmp_path / "nonexistent.json",
        ):
            assert _load_config() is None

    def test_invalid_json_returns_none(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "config.json"
        bad_file.write_text("{invalid", encoding="utf-8")
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            bad_file,
        ):
            assert _load_config() is None

    def test_non_object_json_returns_none(self, tmp_path: Path) -> None:
        array_file = tmp_path / "config.json"
        array_file.write_text("[1, 2, 3]", encoding="utf-8")
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            array_file,
        ):
            assert _load_config() is None

    def test_valid_config_returns_dict(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"stage": "generating_data"}),
            encoding="utf-8",
        )
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            config_file,
        ):
            result = _load_config()
            assert result == {"stage": "generating_data"}


class TestRun:
    """Entrypoint _run() error handling."""

    def test_missing_config_returns_1(self, tmp_path: Path) -> None:
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            tmp_path / "nonexistent.json",
        ):
            assert _run() == 1

    def test_unknown_stage_returns_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"stage": "not_a_stage"}),
            encoding="utf-8",
        )
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            config_file,
        ):
            assert _run() == 1

    def test_non_executable_stage_returns_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"stage": "idle"}),
            encoding="utf-8",
        )
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            config_file,
        ):
            assert _run() == 1

    def test_empty_stage_returns_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"stage": ""}),
            encoding="utf-8",
        )
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            config_file,
        ):
            assert _run() == 1

    def test_successful_stage_returns_0(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "stage": "generating_data",
                    "source_dir": "/data",
                    "output_dir": "/checkpoints",
                }
            ),
            encoding="utf-8",
        )
        mock_dispatch = AsyncMock()
        with (
            patch(
                "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
                config_file,
            ),
            patch(
                "synthorg.memory.embedding.fine_tune_runner._dispatch_stage",
                mock_dispatch,
            ),
        ):
            assert _run() == 0
        mock_dispatch.assert_awaited_once()
        captured = capsys.readouterr()
        assert "STAGE_START:generating_data" in captured.out
        assert "STAGE_COMPLETE:generating_data" in captured.out

    def test_stage_exception_returns_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"stage": "generating_data"}),
            encoding="utf-8",
        )
        mock_dispatch = AsyncMock(side_effect=ValueError("bad config"))
        with (
            patch(
                "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
                config_file,
            ),
            patch(
                "synthorg.memory.embedding.fine_tune_runner._dispatch_stage",
                mock_dispatch,
            ),
        ):
            assert _run() == 1

    def test_memory_error_propagates(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"stage": "generating_data"}),
            encoding="utf-8",
        )
        mock_dispatch = AsyncMock(side_effect=MemoryError("OOM"))
        with (
            patch(
                "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
                config_file,
            ),
            patch(
                "synthorg.memory.embedding.fine_tune_runner._dispatch_stage",
                mock_dispatch,
            ),
            pytest.raises(MemoryError),
        ):
            _run()

    def test_recursion_error_propagates(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"stage": "generating_data"}),
            encoding="utf-8",
        )
        mock_dispatch = AsyncMock(side_effect=RecursionError())
        with (
            patch(
                "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
                config_file,
            ),
            patch(
                "synthorg.memory.embedding.fine_tune_runner._dispatch_stage",
                mock_dispatch,
            ),
            pytest.raises(RecursionError),
        ):
            _run()

    def test_missing_stage_key_returns_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"not_stage": "value"}),
            encoding="utf-8",
        )
        with patch(
            "synthorg.memory.embedding.fine_tune_runner._CONFIG_PATH",
            config_file,
        ):
            assert _run() == 1
