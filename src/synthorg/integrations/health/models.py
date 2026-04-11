"""Health check models.

Re-exports ``HealthReport`` and ``ConnectionStatus`` from the
connection models for convenience.
"""

from synthorg.integrations.connections.models import (
    ConnectionStatus,
    HealthReport,
)

__all__ = ["ConnectionStatus", "HealthReport"]
