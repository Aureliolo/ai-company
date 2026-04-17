"""Fine-tune pipeline runtime event constants.

Emitted by the ``synthorg.memory.embedding.fine_tune_runner`` container
entrypoint. Separated from ``events.memory`` so the runner's operational
lifecycle is queryable independently of the memory subsystem.
"""

from typing import Final

FINE_TUNE_HEALTH_SERVER_STARTED: Final[str] = "fine_tune.health_server.started"
FINE_TUNE_HEALTH_SERVER_STOPPED: Final[str] = "fine_tune.health_server.stopped"
FINE_TUNE_HEALTH_SERVER_BIND_FAILED: Final[str] = "fine_tune.health_server.bind_failed"
