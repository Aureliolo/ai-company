"""Tests for PersonalityPresetService."""

import json

import pytest

from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.templates.preset_service import PersonalityPresetService
from synthorg.templates.presets import PERSONALITY_PRESETS
from tests.unit.api.fakes import FakePersonalityPresetRepository


def _make_valid_config() -> dict[str, object]:
    """Return a valid PersonalityConfig dict for testing."""
    return {
        "traits": ("friendly", "curious"),
        "communication_style": "warm",
        "risk_tolerance": "medium",
        "creativity": "high",
        "description": "A test preset",
        "openness": 0.8,
        "conscientiousness": 0.6,
        "extraversion": 0.7,
        "agreeableness": 0.9,
        "stress_response": 0.5,
        "decision_making": "consultative",
        "collaboration": "team",
        "verbosity": "balanced",
        "conflict_approach": "collaborate",
    }


@pytest.fixture
def repo() -> FakePersonalityPresetRepository:
    return FakePersonalityPresetRepository()


@pytest.fixture
def service(
    repo: FakePersonalityPresetRepository,
) -> PersonalityPresetService:
    return PersonalityPresetService(repository=repo)


@pytest.mark.unit
class TestListAll:
    async def test_lists_all_builtins(self, service: PersonalityPresetService) -> None:
        entries = await service.list_all()
        builtin_names = {e.name for e in entries if e.source == "builtin"}
        assert builtin_names == set(PERSONALITY_PRESETS.keys())

    async def test_includes_custom_presets(
        self,
        service: PersonalityPresetService,
        repo: FakePersonalityPresetRepository,
    ) -> None:
        config = _make_valid_config()
        config_json = json.dumps(config, sort_keys=True)
        await repo.save(
            "my_custom",
            config_json,
            "Custom",
            "2026-03-31T00:00:00+00:00",
            "2026-03-31T00:00:00+00:00",
        )
        entries = await service.list_all()
        custom = [e for e in entries if e.source == "custom"]
        assert len(custom) == 1
        assert custom[0].name == "my_custom"

    async def test_sorted_by_name(self, service: PersonalityPresetService) -> None:
        entries = await service.list_all()
        names = [e.name for e in entries]
        assert names == sorted(names)

    async def test_source_tags_correct(self, service: PersonalityPresetService) -> None:
        entries = await service.list_all()
        for entry in entries:
            if entry.name in PERSONALITY_PRESETS:
                assert entry.source == "builtin"


@pytest.mark.unit
class TestGet:
    async def test_get_builtin(self, service: PersonalityPresetService) -> None:
        entry = await service.get("visionary_leader")
        assert entry.source == "builtin"
        assert entry.name == "visionary_leader"
        assert "strategic" in entry.config.get("traits", ())

    async def test_get_builtin_case_insensitive(
        self, service: PersonalityPresetService
    ) -> None:
        entry = await service.get("Visionary_Leader")
        assert entry.name == "visionary_leader"

    async def test_get_custom(
        self,
        service: PersonalityPresetService,
        repo: FakePersonalityPresetRepository,
    ) -> None:
        config = _make_valid_config()
        config_json = json.dumps(config, sort_keys=True)
        await repo.save(
            "my_custom",
            config_json,
            "Custom",
            "2026-03-31T00:00:00+00:00",
            "2026-03-31T00:00:00+00:00",
        )
        entry = await service.get("my_custom")
        assert entry.source == "custom"
        assert entry.created_at == "2026-03-31T00:00:00+00:00"

    async def test_get_not_found(self, service: PersonalityPresetService) -> None:
        with pytest.raises(NotFoundError):
            await service.get("nonexistent_preset")

    async def test_get_blank_name_raises_not_found(
        self, service: PersonalityPresetService
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.get("  ")


@pytest.mark.unit
class TestCreate:
    async def test_create_valid(self, service: PersonalityPresetService) -> None:
        config = _make_valid_config()
        entry = await service.create("my_custom", config)
        assert entry.name == "my_custom"
        assert entry.source == "custom"
        assert entry.created_at is not None
        assert entry.updated_at is not None

    async def test_create_normalizes_name(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        entry = await service.create("  My_Custom  ", config)
        assert entry.name == "my_custom"

    async def test_create_rejects_builtin_shadow(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        with pytest.raises(ConflictError, match="builtin"):
            await service.create("visionary_leader", config)

    async def test_create_rejects_duplicate_custom(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        await service.create("unique_preset", config)
        with pytest.raises(ConflictError, match="already exists"):
            await service.create("unique_preset", config)

    async def test_create_rejects_invalid_config(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        config["openness"] = 2.0  # Out of range
        with pytest.raises(ApiValidationError):
            await service.create("bad_preset", config)

    async def test_create_rejects_invalid_name_format(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        with pytest.raises(ApiValidationError, match="Invalid preset name"):
            await service.create("has spaces", config)

    async def test_create_rejects_empty_name(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        with pytest.raises(ApiValidationError, match="blank"):
            await service.create("  ", config)


@pytest.mark.unit
class TestUpdate:
    async def test_update_existing_custom(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        await service.create("my_preset", config)
        config["openness"] = 0.9
        entry = await service.update("my_preset", config)
        assert entry.config["openness"] == 0.9
        assert entry.source == "custom"

    async def test_update_preserves_created_at(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        created = await service.create("my_preset", config)
        config["openness"] = 0.1
        updated = await service.update("my_preset", config)
        assert updated.created_at == created.created_at
        assert updated.updated_at != created.updated_at

    async def test_update_rejects_builtin(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        with pytest.raises(ConflictError, match="builtin"):
            await service.update("visionary_leader", config)

    async def test_update_not_found(self, service: PersonalityPresetService) -> None:
        config = _make_valid_config()
        with pytest.raises(NotFoundError):
            await service.update("nonexistent", config)

    async def test_update_rejects_invalid_config(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        await service.create("update_invalid", config)
        config["openness"] = 2.0
        with pytest.raises(ApiValidationError):
            await service.update("update_invalid", config)


@pytest.mark.unit
class TestDelete:
    async def test_delete_existing_custom(
        self, service: PersonalityPresetService
    ) -> None:
        config = _make_valid_config()
        await service.create("my_preset", config)
        await service.delete("my_preset")
        with pytest.raises(NotFoundError):
            await service.get("my_preset")

    async def test_delete_rejects_builtin(
        self, service: PersonalityPresetService
    ) -> None:
        with pytest.raises(ConflictError, match="builtin"):
            await service.delete("visionary_leader")

    async def test_delete_not_found(self, service: PersonalityPresetService) -> None:
        with pytest.raises(NotFoundError):
            await service.delete("nonexistent")


@pytest.mark.unit
class TestGetSchema:
    def test_returns_json_schema(self) -> None:
        schema = PersonalityPresetService.get_schema()
        assert "properties" in schema
        assert "openness" in schema["properties"]
        assert "traits" in schema["properties"]
        assert schema["properties"]["openness"]["type"] == "number"
