"""Tests for config defaults."""

import pytest

from ai_company.config.defaults import default_config_dict
from ai_company.config.schema import RootConfig


@pytest.mark.unit
class TestDefaultConfigDict:
    def test_returns_dict(self):
        result = default_config_dict()
        assert isinstance(result, dict)

    def test_required_keys_present(self):
        result = default_config_dict()
        assert "company_name" in result
        assert "company_type" in result
        assert result["company_name"] == "AI Company"
        assert result["company_type"] == "custom"

    def test_constructs_valid_root_config(self):
        data = default_config_dict()
        cfg = RootConfig(**data)
        assert cfg.company_name == "AI Company"
        assert cfg.company_type.value == "custom"

    def test_returns_fresh_dict_each_call(self):
        a = default_config_dict()
        b = default_config_dict()
        assert a == b
        assert a is not b
