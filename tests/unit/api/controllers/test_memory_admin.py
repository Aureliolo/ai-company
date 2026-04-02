"""Tests for MemoryAdminController endpoints."""

import pytest
from pydantic import ValidationError

from synthorg.api.controllers.memory import MemoryAdminController
from synthorg.memory.embedding.fine_tune import FineTuneStage
from synthorg.memory.embedding.fine_tune_models import (
    FineTuneRequest,
    FineTuneStatus,
)


@pytest.mark.unit
class TestFineTuneRequest:
    def test_valid(self) -> None:
        req = FineTuneRequest(source_dir="/data/docs")
        assert req.source_dir == "/data/docs"
        assert req.base_model is None
        assert req.output_dir is None

    def test_rejects_blank_source_dir(self) -> None:
        with pytest.raises(ValidationError, match="whitespace"):
            FineTuneRequest(source_dir="   ")

    def test_full_request(self) -> None:
        req = FineTuneRequest(
            source_dir="/data/docs",
            base_model="test-model",
            output_dir="/output",
        )
        assert req.base_model == "test-model"


@pytest.mark.unit
class TestFineTuneStatus:
    def test_defaults(self) -> None:
        status = FineTuneStatus()
        assert status.stage == FineTuneStage.IDLE
        assert status.progress is None
        assert status.error is None

    def test_valid_progress(self) -> None:
        status = FineTuneStatus(
            stage=FineTuneStage.TRAINING,
            progress=0.5,
        )
        assert status.progress == 0.5

    def test_rejects_progress_above_one(self) -> None:
        with pytest.raises(ValidationError):
            FineTuneStatus(progress=1.5)

    def test_rejects_negative_progress(self) -> None:
        with pytest.raises(ValidationError):
            FineTuneStatus(progress=-0.1)

    def test_rejects_nan_progress(self) -> None:
        with pytest.raises(ValidationError):
            FineTuneStatus(progress=float("nan"))

    def test_rejects_inf_progress(self) -> None:
        with pytest.raises(ValidationError):
            FineTuneStatus(progress=float("inf"))

    def test_with_error(self) -> None:
        status = FineTuneStatus(
            stage=FineTuneStage.FAILED,
            error="pipeline crashed",
        )
        assert status.error == "pipeline crashed"


@pytest.mark.unit
class TestMemoryAdminControllerExists:
    """Verify the controller is correctly defined."""

    def test_path(self) -> None:
        assert MemoryAdminController.path == "/admin/memory"

    def test_tags(self) -> None:
        assert "admin" in MemoryAdminController.tags
        assert "memory" in MemoryAdminController.tags
