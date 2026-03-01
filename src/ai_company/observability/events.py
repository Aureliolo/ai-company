"""Structured event name constants for observability.

All event names follow the ``domain.noun.verb`` convention and are
used as the first positional argument to structured log calls::

    logger.info(CONFIG_LOADED, config_path=path)

Using constants instead of bare strings ensures consistency across
modules and enables grep-based auditing of log coverage.
"""

# ── Config lifecycle ──────────────────────────────────────────────

CONFIG_DISCOVERY_STARTED: str = "config.discovery.started"
CONFIG_DISCOVERY_FOUND: str = "config.discovery.found"
CONFIG_LOADED: str = "config.load.success"
CONFIG_OVERRIDE_APPLIED: str = "config.override.applied"
CONFIG_ENV_VAR_RESOLVED: str = "config.env_var.resolved"
CONFIG_VALIDATION_FAILED: str = "config.validation.failed"
CONFIG_PARSE_FAILED: str = "config.parse.failed"

# ── Provider lifecycle ────────────────────────────────────────────

PROVIDER_REGISTRY_BUILT: str = "provider.registry.built"
PROVIDER_DRIVER_INSTANTIATED: str = "provider.driver.instantiated"
PROVIDER_DRIVER_FACTORY_MISSING: str = "provider.driver.factory_missing"
PROVIDER_DRIVER_NOT_REGISTERED: str = "provider.driver.not_registered"
PROVIDER_CALL_START: str = "provider.call.start"
PROVIDER_CALL_SUCCESS: str = "provider.call.success"
PROVIDER_CALL_ERROR: str = "provider.call.error"
PROVIDER_STREAM_START: str = "provider.stream.start"
PROVIDER_STREAM_DONE: str = "provider.stream.done"
PROVIDER_MODEL_NOT_FOUND: str = "provider.model.not_found"
PROVIDER_COST_COMPUTED: str = "provider.cost.computed"
PROVIDER_CAPABILITIES_FETCHED: str = "provider.capabilities.fetched"
PROVIDER_RATE_LIMITED: str = "provider.rate.limited"
PROVIDER_AUTH_ERROR: str = "provider.auth.error"
PROVIDER_CONNECTION_ERROR: str = "provider.connection.error"

# ── Task state machine ────────────────────────────────────────────

TASK_STATUS_CHANGED: str = "task.status.changed"
TASK_TRANSITION_INVALID: str = "task.transition.invalid"
TASK_TRANSITION_CONFIG_ERROR: str = "task.transition.config_error"

# ── Template lifecycle ────────────────────────────────────────────

TEMPLATE_LOAD_START: str = "template.load.start"
TEMPLATE_LOAD_SUCCESS: str = "template.load.success"
TEMPLATE_LOAD_ERROR: str = "template.load.error"
TEMPLATE_LIST_SKIP_INVALID: str = "template.list.skip_invalid"
TEMPLATE_BUILTIN_DEFECT: str = "template.builtin.defect"
TEMPLATE_RENDER_START: str = "template.render.start"
TEMPLATE_RENDER_SUCCESS: str = "template.render.success"
TEMPLATE_RENDER_VARIABLE_ERROR: str = "template.render.variable_error"
TEMPLATE_RENDER_JINJA2_ERROR: str = "template.render.jinja2_error"
TEMPLATE_RENDER_YAML_ERROR: str = "template.render.yaml_error"
TEMPLATE_RENDER_VALIDATION_ERROR: str = "template.render.validation_error"
TEMPLATE_PERSONALITY_PRESET_UNKNOWN: str = "template.personality_preset.unknown"

# ── Role catalog ──────────────────────────────────────────────────

ROLE_LOOKUP_MISS: str = "role.lookup.miss"
