"""Quantum-safe audit trail with ML-DSA-65 signatures and hash chain.

Public API:

- ``AuditChainSigner`` protocol
- ``AuditChainSink`` (logging handler)
- ``AuditChainVerifier``
- ``AuditChainConfig``
- ``HashChain`` / ``ChainEntry``
"""

from synthorg.observability.audit_chain.chain import ChainEntry, HashChain
from synthorg.observability.audit_chain.config import AuditChainConfig
from synthorg.observability.audit_chain.protocol import AuditChainSigner
from synthorg.observability.audit_chain.sink import AuditChainSink
from synthorg.observability.audit_chain.verifier import AuditChainVerifier

__all__ = [
    "AuditChainConfig",
    "AuditChainSigner",
    "AuditChainSink",
    "AuditChainVerifier",
    "ChainEntry",
    "HashChain",
]
