"""Tests for memory package re-exports."""

import pytest

import synthorg.memory as memory_module


@pytest.mark.unit
class TestMemoryExports:
    def test_all_exports_importable(self) -> None:
        for name in memory_module.__all__:
            assert hasattr(memory_module, name), f"{name} in __all__ but not importable"

    def test_all_has_expected_names(self) -> None:
        expected = {
            "ArchivalMode",
            "ArchivalStore",
            "ContentDensity",
            "DualModeConsolidationStrategy",
            "FusionStrategy",
            "Mem0EmbedderConfig",
            "Mem0MemoryBackend",
            "CompanyMemoryConfig",
            "ConsolidationConfig",
            "ConsolidationResult",
            "ConsolidationStrategy",
            "ContextInjectionStrategy",
            "DefaultTokenEstimator",
            "InjectionPoint",
            "InjectionStrategy",
            "MemoryBackend",
            "MemoryCapabilities",
            "MemoryCapabilityError",
            "MemoryConfigError",
            "MemoryConnectionError",
            "MemoryConsolidationService",
            "MemoryEntry",
            "MemoryError",
            "MemoryInjectionStrategy",
            "MemoryMetadata",
            "MemoryNotFoundError",
            "MemoryOptionsConfig",
            "MemoryQuery",
            "MemoryRetrievalConfig",
            "MemoryRetrievalError",
            "MemoryStorageConfig",
            "MemoryStoreError",
            "MemoryStoreRequest",
            "OrgFact",
            "OrgFactAuthor",
            "OrgFactStore",
            "OrgFactWriteRequest",
            "OrgMemoryBackend",
            "OrgMemoryConfig",
            "OrgMemoryError",
            "OrgMemoryQuery",
            "RetentionEnforcer",
            "SQLiteOrgFactStore",
            "ScoredMemory",
            "SharedKnowledgeStore",
            "SimpleConsolidationStrategy",
            "TokenEstimator",
            "create_memory_backend",
            "create_org_memory_backend",
            "fuse_ranked_lists",
        }
        assert set(memory_module.__all__) == expected
