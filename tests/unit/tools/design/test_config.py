"""Tests for design tool configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.tools.design.config import DesignToolsConfig


@pytest.mark.unit
class TestDesignToolsConfig:
    """Tests for DesignToolsConfig."""

    def test_default_values(self) -> None:
        config = DesignToolsConfig()
        assert config.image_timeout == 60.0
        assert config.max_image_size_bytes == 52_428_800
        assert config.asset_storage_path is None

    def test_frozen(self) -> None:
        config = DesignToolsConfig()
        with pytest.raises(ValidationError):
            config.image_timeout = 30.0  # type: ignore[misc]

    def test_custom_values(self) -> None:
        config = DesignToolsConfig(
            image_timeout=120.0,
            max_image_size_bytes=10_000_000,
            asset_storage_path="/var/data/assets",
        )
        assert config.image_timeout == 120.0
        assert config.max_image_size_bytes == 10_000_000
        assert config.asset_storage_path == "/var/data/assets"

    def test_image_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            DesignToolsConfig(image_timeout=0)

    def test_image_timeout_max(self) -> None:
        with pytest.raises(ValidationError):
            DesignToolsConfig(image_timeout=601.0)

    def test_max_image_size_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            DesignToolsConfig(max_image_size_bytes=0)

    def test_rejects_nan(self) -> None:
        with pytest.raises(ValidationError):
            DesignToolsConfig(image_timeout=float("nan"))

    def test_rejects_inf(self) -> None:
        with pytest.raises(ValidationError):
            DesignToolsConfig(image_timeout=float("inf"))

    def test_blank_storage_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DesignToolsConfig(asset_storage_path="   ")
