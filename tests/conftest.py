"""Root test configuration and shared fixtures."""

import logging
import os

import structlog
from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "dev",
    max_examples=1000,
)
# Configure Hypothesis globally for the test session.
# Override by setting HYPOTHESIS_PROFILE=dev in the environment.
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))


def clear_logging_state() -> None:
    """Clear structlog context and stdlib root handlers.

    Shared helper for observability test fixtures that need to reset
    logging state between tests.
    """
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)
