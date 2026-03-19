"""Setup event constants for structured logging.

Constants follow the ``setup.<entity>.<action>`` naming convention
and are passed as the first argument to ``logger.info()``/``logger.debug()``
calls in the first-run setup flow.
"""

from typing import Final

# Status check
SETUP_STATUS_CHECKED: Final[str] = "setup.status.checked"

# Company creation during setup
SETUP_COMPANY_CREATED: Final[str] = "setup.company.created"

# Agent creation during setup
SETUP_AGENT_CREATED: Final[str] = "setup.agent.created"

# Setup completion
SETUP_COMPLETED: Final[str] = "setup.flow.completed"

# Setup reset (via CLI or settings delete)
SETUP_RESET: Final[str] = "setup.flow.reset"

# Template listing
SETUP_TEMPLATES_LISTED: Final[str] = "setup.templates.listed"

# Agents list read fallback (no existing agents in settings)
SETUP_AGENTS_READ_FALLBACK: Final[str] = "setup.agents.read_fallback"

# Status check fallback (settings service unavailable)
SETUP_STATUS_SETTINGS_UNAVAILABLE: Final[str] = "setup.status.settings_unavailable"
