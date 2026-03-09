"""Shared organizational memory — protocols, models, config, and factory.

Re-exports the public API so consumers can import from
``ai_company.memory.org`` directly.
"""

from ai_company.memory.org.access_control import (
    CategoryWriteRule,
    WriteAccessConfig,
    check_write_access,
    require_write_access,
)
from ai_company.memory.org.config import ExtendedStoreConfig, OrgMemoryConfig
from ai_company.memory.org.errors import (
    OrgMemoryAccessDeniedError,
    OrgMemoryConfigError,
    OrgMemoryConnectionError,
    OrgMemoryError,
    OrgMemoryQueryError,
    OrgMemoryWriteError,
)
from ai_company.memory.org.factory import create_org_memory_backend
from ai_company.memory.org.hybrid_backend import HybridPromptRetrievalBackend
from ai_company.memory.org.models import (
    OrgFact,
    OrgFactAuthor,
    OrgFactWriteRequest,
    OrgMemoryQuery,
)
from ai_company.memory.org.protocol import OrgMemoryBackend
from ai_company.memory.org.store import OrgFactStore, SQLiteOrgFactStore

__all__ = [
    "CategoryWriteRule",
    "ExtendedStoreConfig",
    "HybridPromptRetrievalBackend",
    "OrgFact",
    "OrgFactAuthor",
    "OrgFactStore",
    "OrgFactWriteRequest",
    "OrgMemoryAccessDeniedError",
    "OrgMemoryBackend",
    "OrgMemoryConfig",
    "OrgMemoryConfigError",
    "OrgMemoryConnectionError",
    "OrgMemoryError",
    "OrgMemoryQuery",
    "OrgMemoryQueryError",
    "OrgMemoryWriteError",
    "SQLiteOrgFactStore",
    "WriteAccessConfig",
    "check_write_access",
    "create_org_memory_backend",
    "require_write_access",
]
