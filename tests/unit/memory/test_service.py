"""Unit tests for :class:`MemoryService`.

Exercises the in-process logic of the service layer (deploy / rollback
orchestration, rollback bookkeeping, JSON-backup validation, not-found
surfacing) against in-memory fakes so each case runs in milliseconds.
Integration-level behaviour against the real SQLite repo lives in the
conformance suite.
"""

from datetime import UTC, datetime

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.memory.embedding.fine_tune_models import CheckpointRecord
from synthorg.memory.service import (
    CheckpointNotFoundError,
    CheckpointRollbackCorruptError,
    CheckpointRollbackUnavailableError,
    MemoryService,
)
from synthorg.persistence.errors import QueryError
from synthorg.settings.enums import SettingNamespace, SettingSource
from synthorg.settings.errors import SettingNotFoundError
from synthorg.settings.models import SettingValue

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)


def _checkpoint(
    *,
    checkpoint_id: str = "ckpt-1",
    is_active: bool = False,
    backup_config_json: str | None = None,
) -> CheckpointRecord:
    return CheckpointRecord(
        id=NotBlankStr(checkpoint_id),
        run_id=NotBlankStr("run-1"),
        model_path=NotBlankStr("local/models/ckpt-1"),
        base_model=NotBlankStr("example-small-001"),
        doc_count=10,
        eval_metrics=None,
        size_bytes=1024,
        created_at=_NOW,
        is_active=is_active,
        backup_config_json=backup_config_json,
    )


class _FakeCheckpointRepo:
    """Minimal in-memory ``FineTuneCheckpointRepository`` fake."""

    def __init__(self) -> None:
        self._rows: dict[str, CheckpointRecord] = {}
        self.set_active_calls: list[str] = []
        self.deactivate_all_calls: int = 0

    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        self._rows[str(checkpoint.id)] = checkpoint

    async def get_checkpoint(
        self,
        checkpoint_id: str,
    ) -> CheckpointRecord | None:
        return self._rows.get(str(checkpoint_id))

    async def list_checkpoints(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[tuple[CheckpointRecord, ...], int]:
        values = tuple(self._rows.values())
        return values[offset : offset + limit], len(values)

    async def set_active(self, checkpoint_id: str) -> None:
        self.set_active_calls.append(checkpoint_id)
        for key, row in list(self._rows.items()):
            self._rows[key] = row.model_copy(
                update={"is_active": key == checkpoint_id},
            )

    async def deactivate_all(self) -> None:
        self.deactivate_all_calls += 1
        for key, row in list(self._rows.items()):
            self._rows[key] = row.model_copy(update={"is_active": False})

    async def delete_checkpoint(self, checkpoint_id: str) -> None:
        self._rows.pop(str(checkpoint_id), None)

    async def get_active_checkpoint(self) -> CheckpointRecord | None:
        for row in self._rows.values():
            if row.is_active:
                return row
        return None


class _FakeRunRepo:
    """Minimal in-memory ``FineTuneRunRepository`` fake (read-only)."""

    async def save_run(self, run: object) -> None:  # pragma: no cover - unused
        pass

    async def get_run(self, run_id: str) -> None:  # pragma: no cover - unused
        return None

    async def get_active_run(self) -> None:  # pragma: no cover - unused
        return None

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[tuple[()], int]:
        return (), 0

    async def update_run(self, run: object) -> None:  # pragma: no cover - unused
        pass

    async def mark_interrupted(self) -> int:  # pragma: no cover - unused
        return 0


class _FakeSettingsService:
    """Records set/get/delete calls so assertions can verify rollback."""

    def __init__(
        self,
        *,
        initial: dict[tuple[str, str], str] | None = None,
        missing_keys: set[tuple[str, str]] | None = None,
    ) -> None:
        self._values: dict[tuple[str, str], str] = dict(initial or {})
        self._missing = set(missing_keys or ())
        self.set_calls: list[tuple[str, str, str]] = []
        self.delete_calls: list[tuple[str, str]] = []
        self.fail_next_set_keys: set[tuple[str, str]] = set()

    async def get(self, namespace: str, key: str) -> SettingValue:
        if (namespace, key) in self._missing:
            msg = f"Unknown setting: {namespace}/{key}"
            raise SettingNotFoundError(msg)
        if (namespace, key) not in self._values:
            msg = f"Unknown setting: {namespace}/{key}"
            raise SettingNotFoundError(msg)
        return SettingValue(
            namespace=SettingNamespace(namespace),
            key=NotBlankStr(key),
            value=self._values[(namespace, key)],
            source=SettingSource.DATABASE,
            updated_at=None,
        )

    async def set(self, namespace: str, key: str, value: str) -> None:
        if (namespace, key) in self.fail_next_set_keys:
            self.fail_next_set_keys.discard((namespace, key))
            msg = f"set({namespace}, {key}) configured to fail"
            raise RuntimeError(msg)
        self.set_calls.append((namespace, key, value))
        self._values[(namespace, key)] = value

    async def delete(self, namespace: str, key: str) -> None:
        self.delete_calls.append((namespace, key))
        self._values.pop((namespace, key), None)


class TestMemoryServiceCheckpoints:
    """Happy-path coverage for list / get / delete."""

    async def test_list_checkpoints_returns_page(self) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(_checkpoint(checkpoint_id="a"))
        await repo.save_checkpoint(_checkpoint(checkpoint_id="b"))
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )

        page = await service.list_checkpoints(limit=10, offset=0)
        assert {c.id for c in page} == {"a", "b"}

    async def test_get_checkpoint_miss_returns_none(self) -> None:
        service = MemoryService(
            checkpoint_repo=_FakeCheckpointRepo(),
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )
        assert await service.get_checkpoint(NotBlankStr("ghost")) is None

    async def test_delete_missing_raises_not_found(self) -> None:
        service = MemoryService(
            checkpoint_repo=_FakeCheckpointRepo(),
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )
        with pytest.raises(CheckpointNotFoundError):
            await service.delete_checkpoint(NotBlankStr("ghost"))

    async def test_delete_existing_delegates_to_repo(self) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(_checkpoint(checkpoint_id="a"))
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )
        await service.delete_checkpoint(NotBlankStr("a"))
        assert await repo.get_checkpoint("a") is None


class TestMemoryServiceDeploy:
    """``deploy_checkpoint`` happy + rollback paths."""

    async def test_deploy_missing_raises_not_found(self) -> None:
        service = MemoryService(
            checkpoint_repo=_FakeCheckpointRepo(),
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )
        with pytest.raises(CheckpointNotFoundError):
            await service.deploy_checkpoint(NotBlankStr("ghost"))

    async def test_deploy_without_settings_service_activates_only(self) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(_checkpoint(checkpoint_id="a"))
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )

        updated = await service.deploy_checkpoint(NotBlankStr("a"))
        assert updated.is_active is True
        assert repo.set_active_calls == ["a"]

    async def test_deploy_with_settings_pushes_embedder_config(self) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(_checkpoint(checkpoint_id="a"))
        settings = _FakeSettingsService()
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=settings,  # type: ignore[arg-type]
        )

        await service.deploy_checkpoint(NotBlankStr("a"))
        assert ("memory", "embedder_model", "local/models/ckpt-1") in settings.set_calls
        assert ("memory", "embedder_provider", "local") in settings.set_calls

    async def test_deploy_rollback_deletes_newly_written_missing_settings(
        self,
    ) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(_checkpoint(checkpoint_id="a"))
        # No prior value exists for either embedder setting AND the
        # second ``set`` raises -- rollback must explicitly delete
        # ``embedder_model`` so the setting does not remain after
        # rollback.
        settings = _FakeSettingsService(
            missing_keys={
                ("memory", "embedder_model"),
                ("memory", "embedder_provider"),
            },
        )
        settings.fail_next_set_keys.add(("memory", "embedder_provider"))
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=settings,  # type: ignore[arg-type]
        )

        with pytest.raises(RuntimeError):
            await service.deploy_checkpoint(NotBlankStr("a"))

        assert ("memory", "embedder_model") in settings.delete_calls
        assert ("memory", "embedder_provider") in settings.delete_calls
        # The prior checkpoint was deactivated as part of rollback.
        assert repo.deactivate_all_calls >= 1


class TestMemoryServiceRollback:
    """``rollback_checkpoint`` -- unavailable / corrupt / success."""

    async def test_rollback_missing_raises_not_found(self) -> None:
        service = MemoryService(
            checkpoint_repo=_FakeCheckpointRepo(),
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )
        with pytest.raises(CheckpointNotFoundError):
            await service.rollback_checkpoint(NotBlankStr("ghost"))

    async def test_rollback_without_backup_raises_unavailable(self) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(_checkpoint(checkpoint_id="a"))
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )
        with pytest.raises(CheckpointRollbackUnavailableError):
            await service.rollback_checkpoint(NotBlankStr("a"))

    async def test_rollback_with_corrupt_json_raises(self) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(
            _checkpoint(checkpoint_id="a", backup_config_json="{not-json"),
        )
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=_FakeSettingsService(),  # type: ignore[arg-type]
        )
        with pytest.raises(CheckpointRollbackCorruptError):
            await service.rollback_checkpoint(NotBlankStr("a"))

    async def test_rollback_with_non_mapping_json_raises(self) -> None:
        repo = _FakeCheckpointRepo()
        # ``json.loads("[]")`` returns a list, not a dict.
        await repo.save_checkpoint(
            _checkpoint(checkpoint_id="a", backup_config_json="[]"),
        )
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=_FakeSettingsService(),  # type: ignore[arg-type]
        )
        with pytest.raises(CheckpointRollbackCorruptError, match="JSON object"):
            await service.rollback_checkpoint(NotBlankStr("a"))

    async def test_rollback_with_valid_mapping_restores_settings(self) -> None:
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(
            _checkpoint(
                checkpoint_id="a",
                backup_config_json='{"embedder_model": "prev-model"}',
            ),
        )
        settings = _FakeSettingsService()
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=settings,  # type: ignore[arg-type]
        )

        await service.rollback_checkpoint(NotBlankStr("a"))
        assert (
            "memory",
            "embedder_model",
            "prev-model",
        ) in settings.set_calls
        assert repo.deactivate_all_calls == 1

    async def test_rollback_returns_success_when_artifacts_consistent(
        self,
    ) -> None:
        """After rollback, the service re-reads the checkpoint; verify
        the normal return path when all artefacts are consistent.
        """
        repo = _FakeCheckpointRepo()
        await repo.save_checkpoint(
            _checkpoint(
                checkpoint_id="a",
                backup_config_json='{"embedder_model": "prev"}',
            ),
        )
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=_FakeSettingsService(),  # type: ignore[arg-type]
        )
        result = await service.rollback_checkpoint(NotBlankStr("a"))
        assert result.id == "a"


class TestMemoryServiceReReadFailure:
    """``deploy`` detects missing-after-write and raises ``QueryError``."""

    async def test_deploy_raises_when_activation_row_vanishes(self) -> None:
        class _VanishingRepo(_FakeCheckpointRepo):
            def __init__(self) -> None:
                super().__init__()
                self._vanish_after = False

            async def get_checkpoint(
                self,
                checkpoint_id: str,
            ) -> CheckpointRecord | None:
                if self._vanish_after:
                    return None
                return await super().get_checkpoint(checkpoint_id)

            async def set_active(self, checkpoint_id: str) -> None:
                await super().set_active(checkpoint_id)
                # After activation, simulate the row disappearing before
                # the service re-reads it.
                self._vanish_after = True

        repo = _VanishingRepo()
        await repo.save_checkpoint(_checkpoint(checkpoint_id="a"))
        service = MemoryService(
            checkpoint_repo=repo,
            run_repo=_FakeRunRepo(),
            settings_service=None,
        )
        with pytest.raises(QueryError):
            await service.deploy_checkpoint(NotBlankStr("a"))
