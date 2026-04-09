"""Tests for the @ontology_entity decorator."""

import pytest
from pydantic import BaseModel, Field

from synthorg.ontology.decorator import (
    clear_entity_registry,
    get_entity_registry,
    ontology_entity,
)
from synthorg.ontology.errors import OntologyDuplicateError
from synthorg.ontology.models import EntitySource, EntityTier

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Clear the registry before each test."""
    clear_entity_registry()


class TestOntologyEntityDecorator:
    """Tests for @ontology_entity decorator behavior."""

    def test_derives_definition_from_docstring(self) -> None:
        @ontology_entity
        class MyModel(BaseModel):
            """A sample model for testing."""

            name: str

        registry = get_entity_registry()
        assert "MyModel" in registry
        assert registry["MyModel"].definition == "A sample model for testing."

    def test_derives_fields_from_field_descriptions(self) -> None:
        @ontology_entity
        class MyModel(BaseModel):
            """A model."""

            title: str = Field(description="The title")
            count: int = Field(description="The count")
            no_desc: str

        registry = get_entity_registry()
        entity = registry["MyModel"]
        described_names = {f.name for f in entity.fields}
        assert "title" in described_names
        assert "count" in described_names
        assert "no_desc" not in described_names

    def test_field_type_hints_captured(self) -> None:
        @ontology_entity
        class MyModel(BaseModel):
            """A model."""

            name: str = Field(description="Name field")
            age: int = Field(description="Age field")

        entity = get_entity_registry()["MyModel"]
        field_map = {f.name: f for f in entity.fields}
        assert field_map["name"].type_hint == "str"
        assert field_map["age"].type_hint == "int"

    def test_no_docstring_uses_class_name(self) -> None:
        @ontology_entity
        class NoDoc(BaseModel):
            name: str

        entity = get_entity_registry()["NoDoc"]
        assert entity.definition == "NoDoc"

    def test_no_field_descriptions_produces_empty_fields(self) -> None:
        @ontology_entity
        class Bare(BaseModel):
            """A bare model."""

            x: int
            y: str

        entity = get_entity_registry()["Bare"]
        assert entity.fields == ()

    def test_returns_original_class(self) -> None:
        @ontology_entity
        class Original(BaseModel):
            """An original model."""

            value: int

        assert Original.__name__ == "Original"
        instance = Original(value=42)
        assert instance.value == 42

    def test_duplicate_registration_raises(self) -> None:
        @ontology_entity
        class Dup(BaseModel):
            """First."""

        with pytest.raises(OntologyDuplicateError, match="Dup"):

            @ontology_entity
            class Dup(BaseModel):  # type: ignore[no-redef]
                """Second."""

    def test_custom_entity_name(self) -> None:
        @ontology_entity(entity_name="CustomName")
        class Internal(BaseModel):
            """Internal model."""

        registry = get_entity_registry()
        assert "CustomName" in registry
        assert "Internal" not in registry

    def test_custom_tier(self) -> None:
        @ontology_entity(tier=EntityTier.USER)
        class UserEntity(BaseModel):
            """A user entity."""

        entity = get_entity_registry()["UserEntity"]
        assert entity.tier == EntityTier.USER

    def test_custom_source(self) -> None:
        @ontology_entity(source=EntitySource.CONFIG)
        class ConfigEntity(BaseModel):
            """A config entity."""

        entity = get_entity_registry()["ConfigEntity"]
        assert entity.source == EntitySource.CONFIG

    def test_default_tier_is_core(self) -> None:
        @ontology_entity
        class CoreEntity(BaseModel):
            """A core entity."""

        entity = get_entity_registry()["CoreEntity"]
        assert entity.tier == EntityTier.CORE

    def test_default_source_is_auto(self) -> None:
        @ontology_entity
        class AutoEntity(BaseModel):
            """An auto entity."""

        entity = get_entity_registry()["AutoEntity"]
        assert entity.source == EntitySource.AUTO

    def test_clear_empties_registry(self) -> None:
        @ontology_entity
        class Temp(BaseModel):
            """Temp."""

        assert len(get_entity_registry()) == 1
        clear_entity_registry()
        assert len(get_entity_registry()) == 0

    def test_registry_is_read_only(self) -> None:
        @ontology_entity
        class ReadOnly(BaseModel):
            """Read only."""

        registry = get_entity_registry()
        with pytest.raises(TypeError):
            registry["new"] = None  # type: ignore[index]

    def test_multiline_docstring_strips_whitespace(self) -> None:
        @ontology_entity
        class Multi(BaseModel):
            """A model with
            multiple lines in its
            docstring.
            """

        entity = get_entity_registry()["Multi"]
        assert "A model with" in entity.definition
        assert entity.definition.strip() == entity.definition

    def test_complex_type_hints(self) -> None:
        @ontology_entity
        class Complex(BaseModel):
            """Complex types."""

            items: list[str] = Field(description="A list of strings")
            mapping: dict[str, int] = Field(description="A mapping")

        entity = get_entity_registry()["Complex"]
        field_map = {f.name: f for f in entity.fields}
        assert "list" in field_map["items"].type_hint
        assert "dict" in field_map["mapping"].type_hint
