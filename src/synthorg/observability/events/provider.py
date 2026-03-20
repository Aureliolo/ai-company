"""Provider event constants."""

from typing import Final

# ── Provider lifecycle ────────────────────────────────────────────

PROVIDER_REGISTRY_BUILT: Final[str] = "provider.registry.built"
PROVIDER_DRIVER_INSTANTIATED: Final[str] = "provider.driver.instantiated"
PROVIDER_DRIVER_FACTORY_MISSING: Final[str] = "provider.driver.factory_missing"
PROVIDER_DRIVER_NOT_REGISTERED: Final[str] = "provider.driver.not_registered"
PROVIDER_CALL_START: Final[str] = "provider.call.start"
PROVIDER_CALL_SUCCESS: Final[str] = "provider.call.success"
PROVIDER_CALL_ERROR: Final[str] = "provider.call.error"
PROVIDER_STREAM_START: Final[str] = "provider.stream.start"
PROVIDER_STREAM_DONE: Final[str] = "provider.stream.done"
PROVIDER_STREAM_CHUNK_NO_DELTA: Final[str] = "provider.stream.chunk_no_delta"
PROVIDER_MODEL_NOT_FOUND: Final[str] = "provider.model.not_found"
PROVIDER_RATE_LIMITED: Final[str] = "provider.rate.limited"
PROVIDER_AUTH_ERROR: Final[str] = "provider.auth.error"
PROVIDER_CONNECTION_ERROR: Final[str] = "provider.connection.error"
PROVIDER_RETRY_AFTER_PARSE_FAILED: Final[str] = "provider.retry_after.parse_failed"
PROVIDER_MODEL_INFO_UNAVAILABLE: Final[str] = "provider.model_info.unavailable"
PROVIDER_MODEL_INFO_UNEXPECTED_ERROR: Final[str] = (
    "provider.model_info.unexpected_error"
)
PROVIDER_TOOL_CALL_ARGUMENTS_TRUNCATED: Final[str] = (
    "provider.tool_call.arguments_truncated"
)
PROVIDER_TOOL_CALL_INCOMPLETE: Final[str] = "provider.tool_call.incomplete"
PROVIDER_TOOL_CALL_ARGUMENTS_PARSE_FAILED: Final[str] = (
    "provider.tool_call.arguments_parse_failed"
)
PROVIDER_TOOL_CALL_MISSING_FUNCTION: Final[str] = "provider.tool_call.missing_function"
PROVIDER_FINISH_REASON_UNKNOWN: Final[str] = "provider.finish_reason.unknown"

# ── Provider resilience ──────────────────────────────────────────

PROVIDER_RETRY_ATTEMPT: Final[str] = "provider.retry.attempt"
PROVIDER_RETRY_EXHAUSTED: Final[str] = "provider.retry.exhausted"
PROVIDER_RETRY_SKIPPED: Final[str] = "provider.retry.skipped"
PROVIDER_RATE_LIMITER_THROTTLED: Final[str] = "provider.rate_limiter.throttled"
PROVIDER_RATE_LIMITER_PAUSED: Final[str] = "provider.rate_limiter.paused"

# ── Provider management ─────────────────────────────────────

PROVIDER_CREATED: Final[str] = "provider.management.created"
PROVIDER_UPDATED: Final[str] = "provider.management.updated"
PROVIDER_DELETED: Final[str] = "provider.management.deleted"
PROVIDER_CONNECTION_TESTED: Final[str] = "provider.management.connection_tested"
PROVIDER_NOT_FOUND: Final[str] = "provider.management.not_found"
PROVIDER_ALREADY_EXISTS: Final[str] = "provider.management.already_exists"
PROVIDER_VALIDATION_FAILED: Final[str] = "provider.management.validation_failed"

# ── Provider model discovery ───────────────────────────────

PROVIDER_MODELS_DISCOVERED: Final[str] = "provider.management.models_discovered"
PROVIDER_DISCOVERY_FAILED: Final[str] = "provider.management.discovery_failed"
PROVIDER_DISCOVERY_SSRF_BYPASSED: Final[str] = (
    "provider.management.discovery_ssrf_bypassed"
)

# ── Provider URL probing ──────────────────────────────────

PROVIDER_PROBE_STARTED: Final[str] = "provider.management.probe_started"
PROVIDER_PROBE_HIT: Final[str] = "provider.management.probe_hit"
PROVIDER_PROBE_MISS: Final[str] = "provider.management.probe_miss"
PROVIDER_PROBE_COMPLETED: Final[str] = "provider.management.probe_completed"
