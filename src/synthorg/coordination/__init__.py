"""MCP-facing coordination service layer.

Wraps :class:`CoordinationMetricsStore` so the MCP tools
``synthorg_coordination_get_task_metrics`` and
``synthorg_coordination_metrics_list`` have a single entry point for
reading coordination telemetry.

Triggering a full coordination run (the engine-loop-internal
pipeline) is intentionally not exposed through this facade; rebuilding
a full :class:`CoordinationContext` in the handler layer would couple
MCP to every engine internal. Coordination is triggered over REST
via ``POST /tasks/{task_id}/coordinate``; MCP callers inspect the
metrics the engine records after each run.
"""

from synthorg.coordination.service import CoordinationService

__all__ = ["CoordinationService"]
