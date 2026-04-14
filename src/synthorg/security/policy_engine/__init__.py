"""Policy engine -- runtime pre-execution gate for tool and delegation actions.

Public API:

- ``PolicyEngine`` protocol
- ``CedarPolicyEngine`` (Cedar adapter via ``cedarpy``)
- ``PolicyActionRequest`` / ``PolicyDecision`` models
- ``SecurityPolicyConfig`` configuration
- ``build_policy_engine`` factory
"""

from synthorg.security.policy_engine.cedar_engine import CedarPolicyEngine
from synthorg.security.policy_engine.config import (
    SecurityPolicyConfig,
    build_policy_engine,
)
from synthorg.security.policy_engine.models import (
    PolicyActionRequest,
    PolicyDecision,
)
from synthorg.security.policy_engine.protocol import PolicyEngine

__all__ = [
    "CedarPolicyEngine",
    "PolicyActionRequest",
    "PolicyDecision",
    "PolicyEngine",
    "SecurityPolicyConfig",
    "build_policy_engine",
]
