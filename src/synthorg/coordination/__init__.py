"""MCP-facing coordination service layer.

Wraps :class:`CoordinationMetricsStore` + the multi-agent coordinator
so the MCP tools ``synthorg_coordination_coordinate_task`` and
``synthorg_coordination_metrics_list`` have a single entry point.

Triggering full coordination (the engine-loop-internal pipeline) is
not exposed through this facade; MCP callers inspect the metrics the
engine already records. The decision is documented in the META-MCP-4
plan -- rebuilding a full :class:`CoordinationContext` in the
handler layer would couple MCP to every engine internal.
"""

from synthorg.coordination.service import CoordinationService

__all__ = ["CoordinationService"]
