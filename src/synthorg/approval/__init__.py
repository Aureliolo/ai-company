"""Shared approval types and protocols.

A neutral subsystem module so ``engine`` and ``tools`` can both depend on
approval event models (``EscalationInfo``, ``ResumePayload``) and on the
``ApprovalStoreProtocol`` contract without either module importing the
other.  This avoids the former cycle that was dodged by ``TYPE_CHECKING``
imports and deferred runtime imports inside function bodies.

The concrete ``ApprovalStore`` implementation lives in
``synthorg.api.approval_store``; concrete ``ApprovalRepository``
implementations live under ``synthorg.persistence.{sqlite,postgres}``.
Callers depending on the protocol types here remain backend-agnostic.
"""

from synthorg.approval.models import EscalationInfo, ResumePayload
from synthorg.approval.protocol import ApprovalStoreProtocol

__all__ = [
    "ApprovalStoreProtocol",
    "EscalationInfo",
    "ResumePayload",
]
