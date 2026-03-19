"""Tests for backup domain models."""

import pytest
from pydantic import ValidationError

from synthorg.backup.models import (
    BackupComponent,
    BackupInfo,
    BackupManifest,
    BackupTrigger,
    RestoreRequest,
    RestoreResponse,
)

pytestmark = pytest.mark.timeout(30)


# -- BackupTrigger enum ------------------------------------------------------


@pytest.mark.unit
class TestBackupTrigger:
    def test_has_five_members(self) -> None:
        assert len(BackupTrigger) == 5

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (BackupTrigger.SCHEDULED, "scheduled"),
            (BackupTrigger.MANUAL, "manual"),
            (BackupTrigger.SHUTDOWN, "shutdown"),
            (BackupTrigger.STARTUP, "startup"),
            (BackupTrigger.PRE_MIGRATION, "pre_migration"),
        ],
    )
    def test_string_values(self, member: BackupTrigger, value: str) -> None:
        assert member.value == value
        assert str(member) == value

    def test_is_str_enum(self) -> None:
        assert isinstance(BackupTrigger.MANUAL, str)


# -- BackupComponent enum ----------------------------------------------------


@pytest.mark.unit
class TestBackupComponent:
    def test_has_three_members(self) -> None:
        assert len(BackupComponent) == 3

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (BackupComponent.PERSISTENCE, "persistence"),
            (BackupComponent.MEMORY, "memory"),
            (BackupComponent.CONFIG, "config"),
        ],
    )
    def test_string_values(self, member: BackupComponent, value: str) -> None:
        assert member.value == value
        assert str(member) == value

    def test_is_str_enum(self) -> None:
        assert isinstance(BackupComponent.PERSISTENCE, str)


# -- BackupManifest -----------------------------------------------------------


@pytest.mark.unit
class TestBackupManifest:
    def test_creation_with_all_fields(self, sample_manifest: BackupManifest) -> None:
        assert sample_manifest.synthorg_version == "0.3.2"
        assert sample_manifest.trigger == BackupTrigger.MANUAL
        assert sample_manifest.size_bytes == 1024
        assert sample_manifest.backup_id == "aabbccdd0011"

    def test_components_are_tuple(self, sample_manifest: BackupManifest) -> None:
        assert isinstance(sample_manifest.components, tuple)
        assert len(sample_manifest.components) == 3

    def test_serialization_roundtrip(self, sample_manifest: BackupManifest) -> None:
        data = sample_manifest.model_dump()
        restored = BackupManifest.model_validate(data)
        assert restored == sample_manifest

    def test_json_roundtrip(self, sample_manifest: BackupManifest) -> None:
        json_str = sample_manifest.model_dump_json()
        restored = BackupManifest.model_validate_json(json_str)
        assert restored == sample_manifest

    def test_frozen(self, sample_manifest: BackupManifest) -> None:
        with pytest.raises(ValidationError):
            sample_manifest.synthorg_version = "99"  # type: ignore[misc]

    def test_rejects_negative_size_bytes(self) -> None:
        with pytest.raises(ValidationError):
            BackupManifest(
                synthorg_version="0.3.2",
                timestamp="2026-03-18T12:00:00+00:00",
                trigger=BackupTrigger.MANUAL,
                components=(BackupComponent.CONFIG,),
                size_bytes=-1,
                checksum="sha256:" + "b" * 64,
                backup_id="aabbccdd0099",
            )

    def test_rejects_blank_backup_id(self) -> None:
        with pytest.raises(ValidationError):
            BackupManifest(
                synthorg_version="0.3.2",
                timestamp="2026-03-18T12:00:00+00:00",
                trigger=BackupTrigger.MANUAL,
                components=(BackupComponent.CONFIG,),
                size_bytes=100,
                checksum="sha256:" + "b" * 64,
                backup_id="",
            )

    def test_rejects_invalid_timestamp(self) -> None:
        with pytest.raises(ValidationError, match="Invalid ISO 8601"):
            BackupManifest(
                synthorg_version="0.3.2",
                timestamp="not-a-date",
                trigger=BackupTrigger.MANUAL,
                components=(BackupComponent.CONFIG,),
                size_bytes=100,
                checksum="sha256:" + "b" * 64,
                backup_id="aabbccdd0099",
            )

    def test_rejects_invalid_checksum_format(self) -> None:
        with pytest.raises(ValidationError, match="sha256:<64-hex-chars>"):
            BackupManifest(
                synthorg_version="0.3.2",
                timestamp="2026-03-18T12:00:00+00:00",
                trigger=BackupTrigger.MANUAL,
                components=(BackupComponent.CONFIG,),
                size_bytes=100,
                checksum="sha256:tooshort",
                backup_id="aabbccdd0099",
            )


# -- BackupInfo ---------------------------------------------------------------


@pytest.mark.unit
class TestBackupInfo:
    def test_creation(self) -> None:
        info = BackupInfo(
            backup_id="aabbccdd0011",
            timestamp="2026-03-18T12:00:00+00:00",
            trigger=BackupTrigger.SCHEDULED,
            components=(BackupComponent.PERSISTENCE,),
            size_bytes=2048,
            compressed=True,
        )
        assert info.backup_id == "aabbccdd0011"
        assert info.trigger == BackupTrigger.SCHEDULED
        assert info.compressed is True
        assert info.size_bytes == 2048

    def test_frozen(self) -> None:
        info = BackupInfo(
            backup_id="aabbccdd0011",
            timestamp="2026-03-18T12:00:00+00:00",
            trigger=BackupTrigger.MANUAL,
            components=(BackupComponent.CONFIG,),
            size_bytes=0,
            compressed=False,
        )
        with pytest.raises(ValidationError):
            info.compressed = True  # type: ignore[misc]

    def test_rejects_negative_size_bytes(self) -> None:
        with pytest.raises(ValidationError):
            BackupInfo(
                backup_id="aabbccdd0011",
                timestamp="2026-03-18T12:00:00+00:00",
                trigger=BackupTrigger.MANUAL,
                components=(),
                size_bytes=-10,
                compressed=False,
            )


# -- RestoreRequest -----------------------------------------------------------


@pytest.mark.unit
class TestRestoreRequest:
    def test_confirm_defaults_false(self) -> None:
        req = RestoreRequest(backup_id="aabbccdd0011")
        assert req.confirm is False

    def test_components_defaults_none(self) -> None:
        req = RestoreRequest(backup_id="aabbccdd0011")
        assert req.components is None

    def test_with_explicit_components(self) -> None:
        req = RestoreRequest(
            backup_id="aabbccdd0011",
            components=(BackupComponent.MEMORY, BackupComponent.CONFIG),
            confirm=True,
        )
        assert req.components == (BackupComponent.MEMORY, BackupComponent.CONFIG)
        assert req.confirm is True

    def test_frozen(self) -> None:
        req = RestoreRequest(backup_id="aabbccdd0011")
        with pytest.raises(ValidationError):
            req.confirm = True  # type: ignore[misc]

    def test_rejects_blank_backup_id(self) -> None:
        with pytest.raises(ValidationError):
            RestoreRequest(backup_id="")

    def test_rejects_invalid_backup_id_format(self) -> None:
        with pytest.raises(ValidationError, match="12-character hex"):
            RestoreRequest(backup_id="not-valid-id")


# -- RestoreResponse ----------------------------------------------------------


@pytest.mark.unit
class TestRestoreResponse:
    def test_creation(self, sample_manifest: BackupManifest) -> None:
        resp = RestoreResponse(
            manifest=sample_manifest,
            restored_components=(
                BackupComponent.PERSISTENCE,
                BackupComponent.MEMORY,
            ),
            safety_backup_id="safety-001",
            restart_required=True,
        )
        assert resp.manifest == sample_manifest
        assert len(resp.restored_components) == 2
        assert resp.safety_backup_id == "safety-001"
        assert resp.restart_required is True

    def test_restart_required_defaults_true(
        self, sample_manifest: BackupManifest
    ) -> None:
        resp = RestoreResponse(
            manifest=sample_manifest,
            restored_components=(BackupComponent.CONFIG,),
            safety_backup_id="safety-002",
        )
        assert resp.restart_required is True

    def test_frozen(self, sample_manifest: BackupManifest) -> None:
        resp = RestoreResponse(
            manifest=sample_manifest,
            restored_components=(BackupComponent.CONFIG,),
            safety_backup_id="safety-002",
        )
        with pytest.raises(ValidationError):
            resp.restart_required = False  # type: ignore[misc]
