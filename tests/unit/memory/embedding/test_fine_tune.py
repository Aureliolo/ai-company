"""Tests for fine-tuning pipeline stage functions."""

import pytest

from synthorg.memory.embedding.fine_tune import (
    FineTuneStage,
    contrastive_fine_tune,
    deploy_checkpoint,
    generate_training_data,
    mine_hard_negatives,
)


@pytest.mark.unit
class TestFineTuneStage:
    def test_values(self) -> None:
        assert FineTuneStage.IDLE.value == "idle"
        assert FineTuneStage.GENERATING_DATA.value == "generating_data"
        assert FineTuneStage.MINING_NEGATIVES.value == "mining_negatives"
        assert FineTuneStage.TRAINING.value == "training"
        assert FineTuneStage.DEPLOYING.value == "deploying"
        assert FineTuneStage.COMPLETE.value == "complete"
        assert FineTuneStage.FAILED.value == "failed"


@pytest.mark.unit
class TestGenerateTrainingData:
    async def test_rejects_blank_source_dir(self) -> None:
        with pytest.raises(ValueError, match="source_dir"):
            await generate_training_data(
                source_dir="   ",
                output_dir="/output",
            )

    async def test_rejects_blank_output_dir(self) -> None:
        with pytest.raises(ValueError, match="output_dir"):
            await generate_training_data(
                source_dir="/source",
                output_dir="   ",
            )

    async def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="training"):
            await generate_training_data(
                source_dir="/source",
                output_dir="/output",
            )


@pytest.mark.unit
class TestMineHardNegatives:
    async def test_rejects_blank_base_model(self) -> None:
        with pytest.raises(ValueError, match="base_model"):
            await mine_hard_negatives(
                training_data_path="/data",
                base_model="   ",
                output_dir="/output",
            )

    async def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="mining"):
            await mine_hard_negatives(
                training_data_path="/data",
                base_model="test-model",
                output_dir="/output",
            )


@pytest.mark.unit
class TestContrastiveFineTune:
    async def test_rejects_zero_epochs(self) -> None:
        with pytest.raises(ValueError, match="epochs"):
            await contrastive_fine_tune(
                training_data_path="/data",
                base_model="test-model",
                output_dir="/output",
                epochs=0,
            )

    async def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="training"):
            await contrastive_fine_tune(
                training_data_path="/data",
                base_model="test-model",
                output_dir="/output",
            )


@pytest.mark.unit
class TestDeployCheckpoint:
    async def test_rejects_blank_checkpoint_path(self) -> None:
        with pytest.raises(ValueError, match="checkpoint_path"):
            await deploy_checkpoint(checkpoint_path="   ")

    async def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="deploy"):
            await deploy_checkpoint(
                checkpoint_path="/models/checkpoint",
            )
