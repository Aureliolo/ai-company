"""Secret backend protocol -- re-exported from the persistence layer.

Canonical definition now lives at
``synthorg.persistence.secret_backends.protocol``; this shim keeps
existing imports working while the rest of the subsystem is folded
into ``src/synthorg/persistence/secret_backends/``.
"""

from synthorg.persistence.secret_backends.protocol import SecretBackend

__all__ = ["SecretBackend"]
