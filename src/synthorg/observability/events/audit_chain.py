"""Audit chain sink internal event constants.

These events intentionally use the ``audit_chain.*`` prefix rather
than ``security.*`` so that logs produced from inside the sink's own
:meth:`AuditChainSink.emit` error paths cannot loop back into the
handler and recurse on the single-worker signing executor. Every
other audit-chain event (signatures, timestamping, integrity checks)
still lives under ``security.*`` because those DO need to be audited.
"""

from typing import Final

AUDIT_CHAIN_EMIT_ERROR: Final[str] = "audit_chain.emit_error"
AUDIT_CHAIN_CALLBACK_ERROR: Final[str] = "audit_chain.callback_error"
