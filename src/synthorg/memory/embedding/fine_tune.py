"""Embedding fine-tuning pipeline stage functions.

Four-stage offline pipeline for domain-specific embedding fine-tuning:

1. Synthetic data generation (LLM-powered, no manual annotation)
2. Hard negative mining (base model embedding + similarity search)
3. Contrastive fine-tuning (InfoNCE loss, biencoder training)
4. Deploy (save checkpoint, update config)

ML dependencies (torch, sentence-transformers) are optional and
guarded with ``ImportError`` messages pointing to the ``fine-tune``
extra.  Actual training logic is not yet implemented -- functions
validate inputs and raise ``NotImplementedError``.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from synthorg.observability import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class FineTuneStage(StrEnum):
    """Fine-tuning pipeline stage status."""

    IDLE = "idle"
    GENERATING_DATA = "generating_data"
    MINING_NEGATIVES = "mining_negatives"
    TRAINING = "training"
    DEPLOYING = "deploying"
    COMPLETE = "complete"
    FAILED = "failed"


def _require_not_blank(value: str, name: str) -> None:
    """Raise ``ValueError`` if *value* is blank."""
    if not value.strip():
        msg = f"{name} must not be blank"
        raise ValueError(msg)


async def generate_training_data(
    source_dir: str,
    output_dir: str,
    *,
    llm_provider: str | None = None,  # noqa: ARG001
) -> Path:
    """Stage 1: Generate synthetic query-document pairs.

    Uses an LLM to generate realistic retrieval queries for each
    document chunk in *source_dir*.  No manual annotation required.

    Args:
        source_dir: Directory containing org documents.
        output_dir: Directory to write training data.
        llm_provider: Optional LLM provider for generation.

    Returns:
        Path to the generated training data file.

    Raises:
        ValueError: If inputs are blank.
        NotImplementedError: Training data generation is not yet
            implemented.
    """
    _require_not_blank(source_dir, "source_dir")
    _require_not_blank(output_dir, "output_dir")
    msg = (
        "Synthetic training data generation is not yet implemented. "
        "See docs/reference/embedding-evaluation.md for the pipeline "
        "design."
    )
    raise NotImplementedError(msg)


async def mine_hard_negatives(
    training_data_path: str,
    base_model: str,
    output_dir: str,
    *,
    top_k: int = 4,  # noqa: ARG001
) -> Path:
    """Stage 2: Mine hard negatives using the base model.

    Embeds all passages with the base model and selects the top-k
    highest-scoring non-positive passages as hard negatives.

    Args:
        training_data_path: Path to training data from Stage 1.
        base_model: Base embedding model identifier.
        output_dir: Directory to write mined negatives.
        top_k: Number of hard negatives per query.

    Returns:
        Path to the training triples file.

    Raises:
        ValueError: If inputs are blank.
        NotImplementedError: Hard negative mining is not yet
            implemented.
    """
    _require_not_blank(training_data_path, "training_data_path")
    _require_not_blank(base_model, "base_model")
    _require_not_blank(output_dir, "output_dir")
    msg = (
        "Hard negative mining is not yet implemented. "
        "See docs/reference/embedding-evaluation.md for the pipeline "
        "design."
    )
    raise NotImplementedError(msg)


async def contrastive_fine_tune(  # noqa: PLR0913
    training_data_path: str,
    base_model: str,
    output_dir: str,
    *,
    epochs: int = 3,
    learning_rate: float = 1e-5,  # noqa: ARG001
    temperature: float = 0.02,  # noqa: ARG001
) -> Path:
    """Stage 3: Contrastive fine-tuning with InfoNCE loss.

    Trains a biencoder on the training triples from Stage 2.

    Args:
        training_data_path: Path to training triples from Stage 2.
        base_model: Base embedding model identifier.
        output_dir: Directory to save the checkpoint.
        epochs: Number of training epochs.
        learning_rate: Learning rate.
        temperature: InfoNCE temperature parameter.

    Returns:
        Path to the saved checkpoint.

    Raises:
        ValueError: If inputs are invalid.
        NotImplementedError: Contrastive training is not yet
            implemented.
    """
    _require_not_blank(training_data_path, "training_data_path")
    _require_not_blank(base_model, "base_model")
    _require_not_blank(output_dir, "output_dir")
    if epochs < 1:
        msg = "epochs must be >= 1"
        raise ValueError(msg)
    msg = (
        "Contrastive training is not yet implemented. "
        "Install the fine-tune extra: pip install synthorg[fine-tune]. "
        "See docs/reference/embedding-evaluation.md for the pipeline "
        "design."
    )
    raise NotImplementedError(msg)


async def deploy_checkpoint(
    checkpoint_path: str,
    config_path: str | None = None,  # noqa: ARG001
) -> None:
    """Stage 4: Deploy a fine-tuned checkpoint.

    Registers the checkpoint with the embedding provider and
    updates the configuration to point to the fine-tuned model.

    Args:
        checkpoint_path: Path to the fine-tuned model checkpoint.
        config_path: Optional config file to update.

    Raises:
        ValueError: If checkpoint_path is blank.
        NotImplementedError: Checkpoint deploy is not yet implemented.
    """
    _require_not_blank(checkpoint_path, "checkpoint_path")
    msg = (
        "Checkpoint deploy is not yet implemented. "
        "See docs/reference/embedding-evaluation.md for the pipeline "
        "design."
    )
    raise NotImplementedError(msg)
