"""Memory error hierarchy.

All memory-related errors inherit from ``MemoryError`` so callers can
catch the entire family with a single except clause.

Note: this shadows the built-in ``MemoryError`` (which signals
out-of-memory conditions in CPython).  Within the ``synthorg``
namespace the domain-specific meaning is unambiguous; callers outside
the package should import explicitly.
"""


class MemoryError(Exception):  # noqa: A001
    """Base exception for all memory operations."""


class MemoryConnectionError(MemoryError):
    """Raised when a backend connection cannot be established or is lost."""


class MemoryStoreError(MemoryError):
    """Raised when a store operation fails."""


class MemoryRetrievalError(MemoryError):
    """Raised when a retrieve or search operation fails."""


class MemoryNotFoundError(MemoryError):
    """Raised when a specific memory ID is not found.

    Note: The ``MemoryBackend.get()`` protocol method returns ``None``
    for missing entries rather than raising this error.  This exception
    is available for concrete backend implementations that need to
    signal "not found" in non-protocol internal methods or batch
    operations.
    """


class MemoryConfigError(MemoryError):
    """Raised when memory configuration is invalid."""


class MemoryCapabilityError(MemoryError):
    """Raised when an unsupported operation is attempted for a backend."""


class FineTuneDependencyError(MemoryError):
    """Raised when fine-tuning ML dependencies are not installed.

    The ``synthorg[fine-tune]`` extra provides ``torch`` and
    ``sentence-transformers``.  This error includes install
    instructions in its message.
    """


class FineTuneCancelledError(MemoryError):
    """Raised when a fine-tuning pipeline run is cancelled."""
