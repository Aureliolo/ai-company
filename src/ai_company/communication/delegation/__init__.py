"""Hierarchical delegation subsystem."""

from ai_company.communication.delegation.authority import (
    AuthorityCheckResult,
    AuthorityValidator,
)
from ai_company.communication.delegation.hierarchy import (
    HierarchyResolver,
)
from ai_company.communication.delegation.models import (
    DelegationRecord,
    DelegationRequest,
    DelegationResult,
)
from ai_company.communication.delegation.service import (
    DelegationService,
)

__all__ = [
    "AuthorityCheckResult",
    "AuthorityValidator",
    "DelegationRecord",
    "DelegationRequest",
    "DelegationResult",
    "DelegationService",
    "HierarchyResolver",
]
