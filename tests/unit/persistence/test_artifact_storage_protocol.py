"""Tests for ArtifactStorageBackend protocol compliance."""

from pathlib import Path

import pytest

from synthorg.persistence.artifact_storage import ArtifactStorageBackend
from synthorg.persistence.filesystem_artifact_storage import (
    FileSystemArtifactStorage,
)


@pytest.mark.unit
class TestArtifactStorageProtocol:
    def test_filesystem_is_artifact_storage_backend(self, tmp_path: Path) -> None:
        storage = FileSystemArtifactStorage(data_dir=tmp_path)
        assert isinstance(storage, ArtifactStorageBackend)

    def test_fake_is_artifact_storage_backend(self) -> None:
        from tests.unit.api.fakes import FakeArtifactStorage

        assert isinstance(FakeArtifactStorage(), ArtifactStorageBackend)
