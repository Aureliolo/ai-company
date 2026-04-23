"""Shared errors for the communication MCP facades.

:class:`CapabilityNotSupportedError` is raised by a facade method whose
underlying primitive does not yet expose the required operation.  The
MCP handler layer catches it and emits a typed ``err(...,
domain_code="not_supported")`` envelope -- different from the legacy
:func:`service_fallback` path because the request reached a real
service before the gap was detected.
"""


class CapabilityNotSupportedError(RuntimeError):
    """Raised when a facade method's underlying primitive cannot satisfy the op.

    Attributes:
        domain_code: Stable wire identifier (``"not_supported"``).
        capability: Which capability was missing; surfaces in the
            error message for operator observability.
    """

    domain_code = "not_supported"

    def __init__(self, capability: str, detail: str) -> None:
        """Initialise with a capability name and reason.

        Args:
            capability: Short identifier for the missing capability.
            detail: Human-readable reason suitable for the error
                envelope's ``message`` field (already scrub-safe since
                it never contains caller-supplied data).
        """
        super().__init__(f"{capability}: {detail}")
        self.capability = capability
