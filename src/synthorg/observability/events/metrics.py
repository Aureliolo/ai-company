"""Metrics event constants for Prometheus and OTLP telemetry.

Event taxonomy for the metrics collection and export subsystem.
"""

from typing import Final

# Prometheus scrape events
METRICS_SCRAPE_COMPLETED: Final[str] = "metrics.scrape.completed"
METRICS_SCRAPE_FAILED: Final[str] = "metrics.scrape.failed"
METRICS_COLLECTOR_INITIALIZED: Final[str] = "metrics.collector.initialized"

# Coordination metrics push events
METRICS_COORDINATION_RECORDED: Final[str] = "metrics.coordination.recorded"

# OTLP export events
METRICS_OTLP_EXPORT_COMPLETED: Final[str] = "metrics.otlp.export_completed"
METRICS_OTLP_EXPORT_FAILED: Final[str] = "metrics.otlp.export_failed"
METRICS_OTLP_FLUSHER_STARTED: Final[str] = "metrics.otlp.flusher_started"
METRICS_OTLP_FLUSHER_STOPPED: Final[str] = "metrics.otlp.flusher_stopped"
