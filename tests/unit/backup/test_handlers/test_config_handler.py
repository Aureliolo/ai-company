"""Tests for ConfigComponentHandler."""

from pathlib import Path
from unittest.mock import patch

import pytest

from synthorg.backup.errors import ComponentBackupError
from synthorg.backup.handlers.config_handler import ConfigComponentHandler
from synthorg.backup.models import BackupComponent

_SAMPLE_YAML = "company:\n  name: test-org\n  departments: []\n"

# -- component property -------------------------------------------------------


@pytest.mark.unit
class TestComponentProperty:
    """ConfigComponentHandler.component returns CONFIG."""

    def test_returns_config(self, tmp_path: Path) -> None:
        handler = ConfigComponentHandler(tmp_path / "company.yaml")
        assert handler.component is BackupComponent.CONFIG


# -- backup --------------------------------------------------------------------


@pytest.mark.unit
class TestBackup:
    """ConfigComponentHandler.backup copies config file."""

    async def test_copies_config_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "company.yaml"
        config_file.write_text(_SAMPLE_YAML)

        target_dir = tmp_path / "backup"
        target_dir.mkdir()

        handler = ConfigComponentHandler(config_file)
        size = await handler.backup(target_dir)

        backup_file = target_dir / "config" / "company.yaml"
        assert backup_file.exists()
        assert backup_file.read_text() == _SAMPLE_YAML
        assert size == backup_file.stat().st_size
        assert size > 0

    async def test_returns_zero_if_source_missing(self, tmp_path: Path) -> None:
        config_file = tmp_path / "nonexistent.yaml"
        handler = ConfigComponentHandler(config_file)

        target_dir = tmp_path / "backup"
        target_dir.mkdir()

        size = await handler.backup(target_dir)
        assert size == 0

    async def test_raises_on_copy_failure(self, tmp_path: Path) -> None:
        config_file = tmp_path / "company.yaml"
        config_file.write_text(_SAMPLE_YAML)

        target_dir = tmp_path / "backup"
        target_dir.mkdir()

        handler = ConfigComponentHandler(config_file)

        with (
            patch(
                "synthorg.backup.handlers.config_handler."
                "ConfigComponentHandler._copy_config",
                side_effect=OSError("disk full"),
            ),
            pytest.raises(ComponentBackupError, match="Failed to back up config"),
        ):
            await handler.backup(target_dir)


# -- restore -------------------------------------------------------------------


@pytest.mark.unit
class TestRestore:
    """ConfigComponentHandler.restore copies file back."""

    async def test_restores_config_file(self, tmp_path: Path) -> None:
        # Set up the "live" config with original content
        live_config = tmp_path / "live" / "company.yaml"
        live_config.parent.mkdir()
        live_config.write_text("original: true\n")

        # Set up the backup with different content
        backup_dir = tmp_path / "backup"
        config_backup_dir = backup_dir / "config"
        config_backup_dir.mkdir(parents=True)
        backup_file = config_backup_dir / "company.yaml"
        backup_file.write_text(_SAMPLE_YAML)

        handler = ConfigComponentHandler(live_config)
        await handler.restore(backup_dir)

        assert live_config.read_text() == _SAMPLE_YAML

    async def test_raises_if_backup_dir_missing(self, tmp_path: Path) -> None:
        handler = ConfigComponentHandler(tmp_path / "company.yaml")
        empty_dir = tmp_path / "empty_backup"
        empty_dir.mkdir()

        with pytest.raises(
            ComponentBackupError,
            match="Backup config directory not found",
        ):
            await handler.restore(empty_dir)

    async def test_raises_if_backup_dir_empty(self, tmp_path: Path) -> None:
        handler = ConfigComponentHandler(tmp_path / "company.yaml")
        backup_dir = tmp_path / "backup"
        config_dir = backup_dir / "config"
        config_dir.mkdir(parents=True)
        # config dir exists but is empty

        with pytest.raises(
            ComponentBackupError,
            match="No config files found",
        ):
            await handler.restore(backup_dir)

    async def test_raises_on_copy_failure(self, tmp_path: Path) -> None:
        live_config = tmp_path / "live" / "company.yaml"
        live_config.parent.mkdir()
        live_config.write_text("original\n")

        backup_dir = tmp_path / "backup"
        config_dir = backup_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "company.yaml").write_text(_SAMPLE_YAML)

        handler = ConfigComponentHandler(live_config)

        with (
            patch(
                "synthorg.backup.handlers.config_handler.shutil.copy2",
                side_effect=PermissionError("no write access"),
            ),
            pytest.raises(ComponentBackupError, match="Failed to restore config"),
        ):
            await handler.restore(backup_dir)


# -- validate_source -----------------------------------------------------------


@pytest.mark.unit
class TestValidateSource:
    """ConfigComponentHandler.validate_source checks for config subdir."""

    async def test_returns_true_when_config_exists_with_files(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "company.yaml").write_text(_SAMPLE_YAML)

        handler = ConfigComponentHandler(tmp_path / "unused.yaml")
        assert await handler.validate_source(tmp_path) is True

    async def test_returns_false_when_config_dir_missing(self, tmp_path: Path) -> None:
        handler = ConfigComponentHandler(tmp_path / "unused.yaml")
        assert await handler.validate_source(tmp_path) is False

    async def test_returns_false_when_config_dir_empty(self, tmp_path: Path) -> None:
        (tmp_path / "config").mkdir()
        handler = ConfigComponentHandler(tmp_path / "unused.yaml")
        assert await handler.validate_source(tmp_path) is False

    async def test_returns_false_for_nonexistent_dir(self, tmp_path: Path) -> None:
        handler = ConfigComponentHandler(tmp_path / "unused.yaml")
        assert await handler.validate_source(tmp_path / "nope") is False
