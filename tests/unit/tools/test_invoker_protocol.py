"""Structural conformance tests for ``ToolInvokerProtocol``.

Locks the runtime-checkable contract against the concrete ``ToolInvoker``
so a future method removal on the concrete fails CI instead of silently
breaking the abstraction for every execution loop.
"""

import pytest

from synthorg.tools.invoker import ToolInvoker
from synthorg.tools.protocol import ToolInvokerProtocol
from synthorg.tools.registry import ToolRegistry

pytestmark = pytest.mark.unit


class TestToolInvokerProtocol:
    """``ToolInvoker`` must satisfy ``ToolInvokerProtocol``."""

    def test_concrete_satisfies_protocol(self) -> None:
        """``isinstance(invoker, ToolInvokerProtocol)`` is True."""
        invoker = ToolInvoker(ToolRegistry([]))
        assert isinstance(invoker, ToolInvokerProtocol)

    def test_protocol_surface_is_stable(self) -> None:
        """The protocol's public method names are the agreed surface."""
        expected = {
            "get_l1_summaries",
            "get_loaded_definitions",
            "invoke",
            "invoke_all",
            "pending_escalations",
            "registry",
        }
        actual = {
            name for name in vars(ToolInvokerProtocol) if not name.startswith("_")
        }
        assert actual == expected, (
            "ToolInvokerProtocol surface changed: "
            f"missing={expected - actual}, added={actual - expected}"
        )
