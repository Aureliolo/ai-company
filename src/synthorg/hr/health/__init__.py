"""Agent health aggregation service layer.

Derives a single "healthy / degraded / unavailable" status per agent
from the existing :class:`PerformanceTracker` snapshot, so MCP
handlers can return a compact health envelope without the caller
having to reconstruct the rollup each time.
"""

from synthorg.hr.health.service import AgentHealthReport, AgentHealthService

__all__ = ["AgentHealthReport", "AgentHealthService"]
