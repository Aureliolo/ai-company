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

# Status check used a default value for a setting (entry absent or not configured)
SETUP_STATUS_SETTINGS_DEFAULT_USED: Final[str] = "setup.status.settings_default_used"

# Provider not found during agent creation
SETUP_PROVIDER_NOT_FOUND: Final[str] = "setup.agent.provider_not_found"

# Model not found in provider during agent creation
SETUP_MODEL_NOT_FOUND: Final[str] = "setup.agent.model_not_found"

# No providers configured when attempting to complete setup
SETUP_NO_PROVIDERS: Final[str] = "setup.flow.no_providers"

# No company created when attempting to complete setup
SETUP_NO_COMPANY: Final[str] = "setup.flow.no_company"

# No agents created when attempting to complete setup
SETUP_NO_AGENTS: Final[str] = "setup.flow.no_agents"

# Template not found during company creation
SETUP_TEMPLATE_NOT_FOUND: Final[str] = "setup.company.template_not_found"

# Template invalid during company creation
SETUP_TEMPLATE_INVALID: Final[str] = "setup.company.template_invalid"

# Mutating endpoint called after setup is already complete
SETUP_ALREADY_COMPLETE: Final[str] = "setup.flow.already_complete"

# Agents list corrupted in settings (JSON parse failure)
SETUP_AGENTS_CORRUPTED: Final[str] = "setup.agents.corrupted"

# Auto-created agents from template during company setup
SETUP_AGENTS_AUTO_CREATED: Final[str] = "setup.agents.auto_created"

# Agents list retrieved for review step
SETUP_AGENTS_LISTED: Final[str] = "setup.agents.listed"

# Agent model assignment updated in review step
SETUP_AGENT_MODEL_UPDATED: Final[str] = "setup.agent.model_updated"

# Agent index out of range during model update
SETUP_AGENT_INDEX_OUT_OF_RANGE: Final[str] = "setup.agent.index_out_of_range"

# Unexpected error while checking setup completion status
SETUP_COMPLETE_CHECK_ERROR: Final[str] = "setup.flow.complete_check_error"

# Agent dict missing critical fields during summary conversion
SETUP_AGENT_SUMMARY_MISSING_FIELDS: Final[str] = "setup.agent.summary_missing_fields"
