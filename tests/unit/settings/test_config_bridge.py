"""Unit tests for config bridge."""

import json

import pytest
from pydantic import BaseModel, ConfigDict

from synthorg.settings.config_bridge import _serialize_value, extract_from_config


class _InnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    daily_limit: float = 10.0
    enabled: bool = True


class _ItemModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = "item"
    value: int = 1


class _FakeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    company_name: str = "TestCo"
    budget: _InnerConfig = _InnerConfig()
    optional_field: str | None = None
    items: tuple[_ItemModel, ...] = ()
    providers: dict[str, _InnerConfig] = {}
    tags: tuple[str, ...] = ()


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestExtractFromConfig:
    """Tests for dotted-path config extraction."""

    def test_top_level_field(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "company_name") == "TestCo"

    def test_nested_field(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "budget.daily_limit") == "10.0"

    def test_nested_bool(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "budget.enabled") == "true"

    def test_missing_top_level(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "nonexistent") is None

    def test_missing_nested(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "budget.nonexistent") is None

    def test_none_field(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "optional_field") is None

    def test_empty_path(self) -> None:
        config = _FakeConfig()
        # Empty string splits to [''] — getattr('') fails
        assert extract_from_config(config, "") is None


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSerializeValue:
    """Tests for _serialize_value() helper."""

    def test_single_model(self) -> None:
        model = _InnerConfig(daily_limit=20.0, enabled=False)
        result = _serialize_value(model)
        parsed = json.loads(result)
        assert parsed == {"daily_limit": 20.0, "enabled": False}

    def test_tuple_of_models(self) -> None:
        items = (
            _ItemModel(name="a", value=1),
            _ItemModel(name="b", value=2),
        )
        result = _serialize_value(items)
        parsed = json.loads(result)
        assert parsed == [
            {"name": "a", "value": 1},
            {"name": "b", "value": 2},
        ]

    def test_dict_of_models(self) -> None:
        providers = {
            "p1": _InnerConfig(daily_limit=5.0),
            "p2": _InnerConfig(daily_limit=15.0),
        }
        result = _serialize_value(providers)
        parsed = json.loads(result)
        assert parsed["p1"]["daily_limit"] == 5.0
        assert parsed["p2"]["daily_limit"] == 15.0

    def test_tuple_of_strings(self) -> None:
        tags = ("alpha", "beta", "gamma")
        result = _serialize_value(tags)
        assert json.loads(result) == ["alpha", "beta", "gamma"]

    def test_empty_tuple(self) -> None:
        result = _serialize_value(())
        assert result == "[]"

    def test_empty_dict(self) -> None:
        result = _serialize_value({})
        assert result == "{}"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("hello", "hello"),
            (42, "42"),
            (3.14, "3.14"),
            (True, "true"),
            (False, "false"),
        ],
    )
    def test_scalar_values(self, value: object, expected: str) -> None:
        assert _serialize_value(value) == expected

    def test_mixed_list_models_and_scalars(self) -> None:
        items = [_ItemModel(name="x", value=1), "plain", 42]
        result = _serialize_value(items)
        parsed = json.loads(result)
        assert parsed == [{"name": "x", "value": 1}, "plain", 42]

    def test_unsupported_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="set"):
            _serialize_value({1, 2, 3})

    def test_mixed_dict_models_and_scalars(self) -> None:
        providers: dict[str, object] = {
            "a": _InnerConfig(daily_limit=5.0),
            "b": "just-a-string",
        }
        result = _serialize_value(providers)
        parsed = json.loads(result)
        assert parsed == {
            "a": {"daily_limit": 5.0, "enabled": True},
            "b": "just-a-string",
        }


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestExtractFromConfigStructural:
    """Tests for extract_from_config with structural data types."""

    def test_single_model_produces_json(self) -> None:
        config = _FakeConfig()
        result = extract_from_config(config, "budget")
        assert result is not None
        parsed = json.loads(result)
        assert parsed == {"daily_limit": 10.0, "enabled": True}

    def test_tuple_of_models_produces_json(self) -> None:
        config = _FakeConfig(
            items=(_ItemModel(name="x", value=9),),
        )
        result = extract_from_config(config, "items")
        assert result is not None
        parsed = json.loads(result)
        assert parsed == [{"name": "x", "value": 9}]

    def test_dict_of_models_produces_json(self) -> None:
        config = _FakeConfig(
            providers={"test": _InnerConfig(daily_limit=7.0)},
        )
        result = extract_from_config(config, "providers")
        assert result is not None
        parsed = json.loads(result)
        assert parsed["test"]["daily_limit"] == 7.0

    def test_empty_tuple_produces_json(self) -> None:
        config = _FakeConfig(items=())
        result = extract_from_config(config, "items")
        assert result == "[]"

    def test_empty_dict_produces_json(self) -> None:
        config = _FakeConfig(providers={})
        result = extract_from_config(config, "providers")
        assert result == "{}"
