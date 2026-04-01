"""Mem0 backend configuration and config builder.

Isolates Mem0-specific settings from the core ``CompanyMemoryConfig``.
The ``build_mem0_config_dict`` function produces the dict that Mem0's
``Memory.from_config()`` expects.
"""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.config import CompanyMemoryConfig  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_BACKEND_CONFIG_INVALID,
)

logger = get_logger(__name__)


class EmbeddingFineTuneConfig(BaseModel):
    """Optional domain-specific embedding fine-tuning configuration.

    Note: checkpoint lookup is not yet implemented in the Mem0
    adapter -- this config prepares the data model for the
    fine-tuning pipeline.

    When checkpoint lookup is implemented, the memory backend will
    look for a fine-tuned model checkpoint at ``checkpoint_path``
    during initialization.  If found, the fine-tuned model will
    override the base ``Mem0EmbedderConfig.model``.  If not found,
    the base model will be used with a logged warning.

    Fine-tuning itself runs offline via a separate pipeline, not
    during backend initialization.  See
    ``docs/reference/embedding-evaluation.md`` for the full
    pipeline design.

    Attributes:
        enabled: Whether fine-tuning checkpoint lookup is active.
        checkpoint_path: Path to the fine-tuned model checkpoint.
            Required when ``enabled`` is ``True``.
        base_model: Identifier of the base model that was fine-tuned.
            Required when ``enabled`` is ``True``.
        training_data_dir: Directory containing training data for
            the offline fine-tuning pipeline.  Not required when
            ``enabled`` is ``True`` -- only consumed by the
            training step, not by checkpoint lookup.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = Field(
        default=False,
        description="Whether fine-tuning checkpoint lookup is active",
    )
    checkpoint_path: NotBlankStr | None = Field(
        default=None,
        description="Path to the fine-tuned model checkpoint",
    )
    base_model: NotBlankStr | None = Field(
        default=None,
        description="Identifier of the base model that was fine-tuned",
    )
    training_data_dir: NotBlankStr | None = Field(
        default=None,
        description=("Directory containing training data for the fine-tuning pipeline"),
    )

    @model_validator(mode="after")
    def _validate_required_when_enabled(self) -> Self:
        """Require checkpoint_path and base_model when fine-tuning is enabled."""
        if self.enabled and self.checkpoint_path is None:
            msg = "checkpoint_path must be set when fine-tuning is enabled"
            logger.warning(
                MEMORY_BACKEND_CONFIG_INVALID,
                model="EmbeddingFineTuneConfig",
                field="checkpoint_path",
                enabled=self.enabled,
                reason=msg,
            )
            raise ValueError(msg)
        if self.enabled and self.base_model is None:
            msg = "base_model must be set when fine-tuning is enabled"
            logger.warning(
                MEMORY_BACKEND_CONFIG_INVALID,
                model="EmbeddingFineTuneConfig",
                field="base_model",
                enabled=self.enabled,
                reason=msg,
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_path_traversal(self) -> Self:
        """Reject parent-directory traversal and Windows paths.

        Consistent with ``Mem0BackendConfig._reject_traversal``.
        """
        for field_name in ("checkpoint_path", "training_data_dir"):
            val = getattr(self, field_name)
            if val is None:
                continue
            parts = PureWindowsPath(val).parts + PurePosixPath(val).parts
            if ".." in parts:
                msg = f"{field_name} must not contain parent-directory traversal (..)"
                logger.warning(
                    MEMORY_BACKEND_CONFIG_INVALID,
                    model="EmbeddingFineTuneConfig",
                    field=field_name,
                    value=val,
                    reason=msg,
                )
                raise ValueError(msg)
            if "\\" in val or (
                len(val) >= 2 and val[1] == ":"  # noqa: PLR2004
            ):
                msg = (
                    f"{field_name} must be a POSIX path (no backslashes "
                    "or drive letters) -- targets Linux containers"
                )
                logger.warning(
                    MEMORY_BACKEND_CONFIG_INVALID,
                    model="EmbeddingFineTuneConfig",
                    field=field_name,
                    value=val,
                    reason=msg,
                )
                raise ValueError(msg)
        return self


class Mem0EmbedderConfig(BaseModel):
    """Embedder settings for the Mem0 memory backend.

    Both ``provider`` and ``model`` are required -- callers must
    supply them explicitly so that vendor-specific identifiers stay
    out of source defaults.  The values must be valid Mem0 SDK
    identifiers (e.g. ``"example-provider"``,
    ``"example-medium-001"``); see the Mem0 documentation for
    supported providers and models.

    Attributes:
        provider: Embedding provider name (Mem0 SDK identifier).
        model: Embedding model identifier (Mem0 SDK identifier).
        dims: Embedding vector dimensions.
        fine_tune: Optional fine-tuning configuration (``None`` by
            default; when provided, disabled unless ``enabled`` is
            ``True``).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    provider: NotBlankStr = Field(
        description="Embedding provider name (Mem0 SDK identifier)",
    )
    model: NotBlankStr = Field(
        description="Embedding model identifier (Mem0 SDK identifier)",
    )
    dims: int = Field(
        default=1536,
        ge=1,
        description="Embedding vector dimensions",
    )
    fine_tune: EmbeddingFineTuneConfig | None = Field(
        default=None,
        description="Optional fine-tuning configuration (None by default)",
    )

    @model_validator(mode="after")
    def _reject_unimplemented_fine_tune(self) -> Self:
        """Reject fine_tune.enabled until checkpoint lookup is implemented."""
        if self.fine_tune is not None and self.fine_tune.enabled:
            msg = (
                "fine_tune.enabled is not yet supported: checkpoint "
                "override is not implemented in the Mem0 adapter"
            )
            logger.warning(
                MEMORY_BACKEND_CONFIG_INVALID,
                model="Mem0EmbedderConfig",
                field="fine_tune.enabled",
                enabled=True,
                reason=msg,
            )
            raise ValueError(msg)
        return self


class Mem0BackendConfig(BaseModel):
    """Mem0-specific backend configuration.

    Attributes:
        data_dir: Directory for Mem0 data persistence.
        collection_name: Qdrant collection name.
        embedder: Embedder settings (required -- no defaults).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    data_dir: NotBlankStr = Field(
        default="/data/memory",
        description="Directory for Mem0 data persistence",
    )
    collection_name: NotBlankStr = Field(
        default="synthorg_memories",
        description="Qdrant collection name",
    )
    embedder: Mem0EmbedderConfig = Field(
        description="Embedder settings",
    )

    @model_validator(mode="after")
    def _reject_traversal(self) -> Self:
        """Reject parent-directory traversal and Windows paths.

        The Mem0 backend targets Linux/Docker containers where paths
        must be POSIX.  Windows-style paths (drive letters, backslashes)
        are rejected to prevent accidental host-path leaks.

        Note: ``build_config_from_company_config`` passes ``data_dir``
        from ``CompanyMemoryConfig``, so this check also protects
        the factory path.
        """
        parts = (
            PureWindowsPath(self.data_dir).parts + PurePosixPath(self.data_dir).parts
        )
        if ".." in parts:
            msg = "data_dir must not contain parent-directory traversal (..)"
            logger.warning(
                MEMORY_BACKEND_CONFIG_INVALID,
                backend="mem0",
                field="data_dir",
                value=self.data_dir,
                reason=msg,
            )
            raise ValueError(msg)
        if "\\" in self.data_dir or (
            len(self.data_dir) >= 2 and self.data_dir[1] == ":"  # noqa: PLR2004  # drive-letter check
        ):
            msg = (
                "data_dir must be a POSIX path (no backslashes or "
                "drive letters) -- the Mem0 backend targets Linux containers"
            )
            logger.warning(
                MEMORY_BACKEND_CONFIG_INVALID,
                backend="mem0",
                field="data_dir",
                value=self.data_dir,
                reason=msg,
            )
            raise ValueError(msg)
        return self


def build_mem0_config_dict(config: Mem0BackendConfig) -> dict[str, Any]:
    """Build the dict that ``Memory.from_config()`` expects.

    Args:
        config: Mem0 backend configuration.

    Returns:
        Configuration dict suitable for ``Memory.from_config()``.
    """
    base_path = PurePosixPath(config.data_dir)
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": config.collection_name,
                "embedding_model_dims": config.embedder.dims,
                "path": str(base_path / "qdrant"),
            },
        },
        "embedder": {
            "provider": config.embedder.provider,
            "config": {
                "model": config.embedder.model,
            },
        },
        "history_db_path": str(base_path / "history.db"),
        # Mem0 config schema version -- required by Memory.from_config().
        "version": "v1.1",
    }


def build_config_from_company_config(
    config: CompanyMemoryConfig,
    *,
    embedder: Mem0EmbedderConfig,
) -> Mem0BackendConfig:
    """Derive a ``Mem0BackendConfig`` from the top-level memory config.

    Args:
        config: Company-wide memory configuration.
        embedder: Embedder settings (provider and model must be
            supplied explicitly to avoid vendor names in defaults).

    Returns:
        Mem0-specific backend configuration.

    Raises:
        ValueError: If the storage config specifies a vector or
            history store that the Mem0 backend does not support,
            or if ``data_dir`` contains parent-directory traversal
            (``..``) -- propagated from ``Mem0BackendConfig``
            validation.
    """
    if config.storage.vector_store != "qdrant":
        msg = (
            f"Mem0 backend only supports embedded qdrant vector store, "
            f"got {config.storage.vector_store!r}"
        )
        logger.warning(
            MEMORY_BACKEND_CONFIG_INVALID,
            backend="mem0",
            field="vector_store",
            value=config.storage.vector_store,
            reason=msg,
        )
        raise ValueError(msg)
    if config.storage.history_store != "sqlite":
        msg = (
            f"Mem0 backend only supports sqlite history store, "
            f"got {config.storage.history_store!r}"
        )
        logger.warning(
            MEMORY_BACKEND_CONFIG_INVALID,
            backend="mem0",
            field="history_store",
            value=config.storage.history_store,
            reason=msg,
        )
        raise ValueError(msg)
    return Mem0BackendConfig(
        data_dir=config.storage.data_dir,
        embedder=embedder,
    )
