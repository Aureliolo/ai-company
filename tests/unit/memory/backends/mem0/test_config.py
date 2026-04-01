"""Tests for Mem0 backend configuration."""

import pytest
from pydantic import ValidationError

from synthorg.memory.backends.mem0.config import (
    EmbeddingFineTuneConfig,
    Mem0BackendConfig,
    Mem0EmbedderConfig,
    build_config_from_company_config,
    build_mem0_config_dict,
)
from synthorg.memory.config import CompanyMemoryConfig, MemoryStorageConfig


def _fine_tune(
    *,
    enabled: bool = True,
    checkpoint_path: str | None = "/models/fine-tuned/checkpoint",
    base_model: str | None = "test-embedding-001",
    training_data_dir: str | None = None,
) -> EmbeddingFineTuneConfig:
    """Build a test fine-tune config with valid defaults."""
    return EmbeddingFineTuneConfig(
        enabled=enabled,
        checkpoint_path=checkpoint_path,
        base_model=base_model,
        training_data_dir=training_data_dir,
    )


def _embedder(
    *,
    provider: str = "test-provider",
    model: str = "test-embedding-001",
    dims: int = 1536,
) -> Mem0EmbedderConfig:
    """Build a test embedder config with vendor-agnostic defaults."""
    return Mem0EmbedderConfig(provider=provider, model=model, dims=dims)


@pytest.mark.unit
class TestEmbeddingFineTuneConfig:
    def test_defaults_disabled(self) -> None:
        config = EmbeddingFineTuneConfig()
        assert config.enabled is False
        assert config.checkpoint_path is None
        assert config.base_model is None
        assert config.training_data_dir is None

    def test_enabled_with_required_fields(self) -> None:
        config = _fine_tune()
        assert config.enabled is True
        assert config.checkpoint_path == "/models/fine-tuned/checkpoint"
        assert config.base_model == "test-embedding-001"

    def test_enabled_requires_checkpoint_path(self) -> None:
        with pytest.raises(ValidationError, match="checkpoint_path"):
            _fine_tune(checkpoint_path=None)

    def test_enabled_requires_base_model(self) -> None:
        with pytest.raises(ValidationError, match="base_model"):
            _fine_tune(base_model=None)

    def test_frozen(self) -> None:
        config = EmbeddingFineTuneConfig()
        with pytest.raises(ValidationError):
            config.enabled = True  # type: ignore[misc]

    @pytest.mark.parametrize(
        "field",
        ["checkpoint_path", "base_model", "training_data_dir"],
    )
    def test_rejects_blank_strings(self, field: str) -> None:
        with pytest.raises(ValidationError):
            EmbeddingFineTuneConfig(**{field: "   "})  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("checkpoint_path", "/models/../escape"),
            ("training_data_dir", "/data/../escape"),
            ("checkpoint_path", "C:\\models\\checkpoint"),
            ("training_data_dir", "D:\\data\\train"),
        ],
        ids=[
            "checkpoint-traversal",
            "training-traversal",
            "checkpoint-windows",
            "training-windows",
        ],
    )
    def test_rejects_unsafe_paths(self, field: str, value: str) -> None:
        with pytest.raises(ValidationError):
            EmbeddingFineTuneConfig(**{field: value})  # type: ignore[arg-type]

    def test_training_data_dir_optional_when_enabled(self) -> None:
        """training_data_dir is intentionally not required when enabled."""
        config = _fine_tune(training_data_dir=None)
        assert config.training_data_dir is None


@pytest.mark.unit
class TestMem0EmbedderConfigFineTune:
    def test_fine_tune_default_none(self) -> None:
        config = _embedder()
        assert config.fine_tune is None

    def test_accepts_disabled_fine_tune(self) -> None:
        config = Mem0EmbedderConfig(
            provider="test-provider",
            model="test-embedding-001",
            fine_tune=EmbeddingFineTuneConfig(),
        )
        assert config.fine_tune is not None
        assert config.fine_tune.enabled is False

    def test_rejects_enabled_fine_tune(self) -> None:
        """fine_tune.enabled=True is not yet supported."""
        with pytest.raises(ValidationError, match="not yet supported"):
            Mem0EmbedderConfig(
                provider="test-provider",
                model="test-embedding-001",
                fine_tune=EmbeddingFineTuneConfig(
                    enabled=True,
                    checkpoint_path="/models/checkpoint",
                    base_model="test-embedding-001",
                ),
            )


@pytest.mark.unit
class TestMem0EmbedderConfig:
    def test_requires_provider_and_model(self) -> None:
        """Provider and model are required -- no vendor-specific defaults."""
        with pytest.raises(ValidationError):
            Mem0EmbedderConfig()  # type: ignore[call-arg]

    def test_custom_values(self) -> None:
        config = Mem0EmbedderConfig(
            provider="test-provider",
            model="test-embedding-001",
            dims=768,
        )
        assert config.provider == "test-provider"
        assert config.model == "test-embedding-001"
        assert config.dims == 768

    def test_default_dims(self) -> None:
        config = _embedder()
        assert config.dims == 1536

    def test_frozen(self) -> None:
        config = _embedder()
        with pytest.raises(ValidationError):
            config.dims = 512  # type: ignore[misc]

    def test_rejects_zero_dims(self) -> None:
        with pytest.raises(ValidationError, match="dims"):
            _embedder(dims=0)

    def test_rejects_blank_provider(self) -> None:
        with pytest.raises(ValidationError):
            Mem0EmbedderConfig(provider="   ", model="test-model")

    def test_rejects_blank_model(self) -> None:
        with pytest.raises(ValidationError):
            Mem0EmbedderConfig(provider="test-provider", model="   ")


@pytest.mark.unit
class TestMem0BackendConfig:
    def test_defaults_with_embedder(self) -> None:
        config = Mem0BackendConfig(embedder=_embedder())
        assert config.data_dir == "/data/memory"
        assert config.collection_name == "synthorg_memories"

    def test_requires_embedder(self) -> None:
        with pytest.raises(ValidationError):
            Mem0BackendConfig()  # type: ignore[call-arg]

    def test_custom_data_dir(self) -> None:
        config = Mem0BackendConfig(
            data_dir="/tmp/test-memory",  # noqa: S108
            embedder=_embedder(),
        )
        assert config.data_dir == "/tmp/test-memory"  # noqa: S108

    def test_custom_collection(self) -> None:
        config = Mem0BackendConfig(
            collection_name="test-collection",
            embedder=_embedder(),
        )
        assert config.collection_name == "test-collection"

    def test_frozen(self) -> None:
        config = Mem0BackendConfig(embedder=_embedder())
        with pytest.raises(ValidationError):
            config.data_dir = "/other"  # type: ignore[misc]

    @pytest.mark.parametrize(
        "data_dir",
        [
            "/data/../escape",
            "C:\\data\\..\\escape",
            "data/../../escape",
        ],
        ids=["unix", "windows", "relative"],
    )
    def test_rejects_parent_traversal(self, data_dir: str) -> None:
        with pytest.raises(ValidationError, match="parent-directory traversal"):
            Mem0BackendConfig(
                data_dir=data_dir,
                embedder=_embedder(),
            )

    def test_accepts_valid_nested_path(self) -> None:
        config = Mem0BackendConfig(
            data_dir="/data/sub/dir",
            embedder=_embedder(),
        )
        assert config.data_dir == "/data/sub/dir"


@pytest.mark.unit
class TestBuildMem0ConfigDict:
    def test_default_config(self) -> None:
        config = Mem0BackendConfig(embedder=_embedder())
        result = build_mem0_config_dict(config)

        assert result["vector_store"]["provider"] == "qdrant"
        assert (
            result["vector_store"]["config"]["collection_name"] == "synthorg_memories"
        )
        assert result["vector_store"]["config"]["embedding_model_dims"] == 1536
        assert result["vector_store"]["config"]["path"] == "/data/memory/qdrant"
        assert result["embedder"]["provider"] == "test-provider"
        assert result["embedder"]["config"]["model"] == "test-embedding-001"
        assert result["history_db_path"] == "/data/memory/history.db"
        assert result["version"] == "v1.1"

    def test_custom_config(self) -> None:
        config = Mem0BackendConfig(
            data_dir="/custom/path",
            collection_name="custom-col",
            embedder=Mem0EmbedderConfig(
                provider="test-provider",
                model="test-model",
                dims=384,
            ),
        )
        result = build_mem0_config_dict(config)

        assert result["vector_store"]["config"]["path"] == "/custom/path/qdrant"
        assert result["vector_store"]["config"]["collection_name"] == "custom-col"
        assert result["vector_store"]["config"]["embedding_model_dims"] == 384
        assert result["embedder"]["provider"] == "test-provider"
        assert result["embedder"]["config"]["model"] == "test-model"
        assert result["history_db_path"] == "/custom/path/history.db"


@pytest.mark.unit
class TestBuildConfigFromCompanyConfig:
    def test_derives_data_dir(self) -> None:
        company_config = CompanyMemoryConfig(backend="mem0")
        mem0_config = build_config_from_company_config(
            company_config,
            embedder=_embedder(),
        )
        assert mem0_config.data_dir == company_config.storage.data_dir

    def test_custom_data_dir(self) -> None:
        company_config = CompanyMemoryConfig(
            backend="mem0",
            storage=MemoryStorageConfig(data_dir="/custom/data"),
        )
        mem0_config = build_config_from_company_config(
            company_config,
            embedder=_embedder(),
        )
        assert mem0_config.data_dir == "/custom/data"

    def test_passes_embedder_through(self) -> None:
        embedder = Mem0EmbedderConfig(
            provider="test-provider",
            model="test-model-xl",
            dims=4096,
        )
        company_config = CompanyMemoryConfig(backend="mem0")
        mem0_config = build_config_from_company_config(
            company_config,
            embedder=embedder,
        )
        assert mem0_config.embedder.provider == "test-provider"
        assert mem0_config.embedder.model == "test-model-xl"
        assert mem0_config.embedder.dims == 4096

    def test_rejects_unsupported_vector_store(self) -> None:
        storage = MemoryStorageConfig.model_construct(
            vector_store="chroma",
            history_store="sqlite",
            data_dir="/data/memory",
        )
        company_config = CompanyMemoryConfig.model_construct(
            backend="mem0",
            storage=storage,
        )
        with pytest.raises(ValueError, match="qdrant"):
            build_config_from_company_config(
                company_config,
                embedder=_embedder(),
            )

    def test_rejects_unsupported_history_store(self) -> None:
        company_config = CompanyMemoryConfig(
            backend="mem0",
            storage=MemoryStorageConfig(history_store="postgresql"),
        )
        with pytest.raises(ValueError, match="sqlite"):
            build_config_from_company_config(
                company_config,
                embedder=_embedder(),
            )

    def test_rejects_qdrant_external(self) -> None:
        """qdrant-external is not supported -- only embedded qdrant."""
        company_config = CompanyMemoryConfig(
            backend="mem0",
            storage=MemoryStorageConfig(vector_store="qdrant-external"),
        )
        with pytest.raises(ValueError, match="embedded qdrant"):
            build_config_from_company_config(
                company_config,
                embedder=_embedder(),
            )
