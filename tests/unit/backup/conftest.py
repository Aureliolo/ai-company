"""Common fixtures for backup unit tests."""

from pathlib import Path

import pytest

from synthorg.backup.config import RetentionConfig
from synthorg.backup.models import (
    BackupComponent,
    BackupManifest,
    BackupTrigger,
)


@pytest.fixture
def retention_config() -> RetentionConfig:
    """RetentionConfig with explicit values for testing."""
    return RetentionConfig(max_count=5, max_age_days=14)


@pytest.fixture
def sample_manifest() -> BackupManifest:
    """A fully-populated BackupManifest for testing."""
    return BackupManifest(
        synthorg_version="0.3.2",
        timestamp="2026-03-18T12:00:00+00:00",
        trigger=BackupTrigger.MANUAL,
        components=(
            BackupComponent.PERSISTENCE,
            BackupComponent.MEMORY,
            BackupComponent.CONFIG,
        ),
        size_bytes=1024,
        checksum="sha256:" + "a" * 64,
        backup_id="aabbccdd0011",
    )


@pytest.fixture
def backup_path(tmp_path: Path) -> Path:
    """Temporary directory for backup storage in tests."""
    bp = tmp_path / "backups"
    bp.mkdir()
    return bp
