---
title: Observability & Performance Tracking
description: Performance tracking configuration, structured logging with 11 default sinks, sensitive-field redaction, correlation IDs, per-domain routing, event taxonomy, third-party logger taming, and runtime-editable settings.
---

# Observability & Performance Tracking

Observability in SynthOrg spans three concerns: performance tracking (quality scoring weights, LLM judge, trend detection), structured logging (11 default sinks with per-domain routing, correlation IDs, sensitive-field redaction), and metrics export (Prometheus `/metrics` + OTLP). All three are configured through the same settings subsystem and refresh without restart where safe.

---

## Performance Tracking Configuration

The `performance` namespace in the company YAML configures the performance tracking
subsystem, including quality scoring weights, LLM judge settings, and trend detection
thresholds. These values flow through `RootConfig.performance` into
`_build_performance_tracker` at app startup.

```yaml
performance:
  min_data_points: 5              # Minimum data points for meaningful aggregation
  windows:
    - "7d"
    - "30d"
    - "90d"
  improving_threshold: 0.05       # Slope threshold for improving trend
  declining_threshold: -0.05      # Slope threshold for declining trend
  quality_judge_model: null       # Model ID for LLM quality judge (null = disabled)
  quality_judge_provider: null    # Provider name (null = auto from first available)
  quality_ci_weight: 0.4          # Weight for CI signal in composite score
  quality_llm_weight: 0.6         # Weight for LLM judge in composite score
  llm_sampling_rate: 0.01         # Fraction of events sampled by LLM calibration
  llm_sampling_model: null        # Model for calibration sampling (null = disabled)
  collaboration_weights: null      # Custom weights for collaboration scoring (null = defaults)
  calibration_retention_days: 90  # Days to retain calibration records
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `quality_judge_model` | `string` or `null` | `null` | Model ID for quality LLM judge. `null` disables the judge. |
| `quality_judge_provider` | `string` or `null` | `null` | Provider name for the judge. Requires `quality_judge_model`. |
| `quality_ci_weight` | `float` | `0.4` | Weight for CI signal (0.0--1.0). Must sum to 1.0 with `quality_llm_weight`. |
| `quality_llm_weight` | `float` | `0.6` | Weight for LLM judge (0.0--1.0). Must sum to 1.0 with `quality_ci_weight`. |
| `min_data_points` | `int` | `5` | Minimum data points for meaningful metric aggregation. |
| `windows` | `list[string]` | `["7d", "30d", "90d"]` | Time window labels for rolling metrics (at least one required). |
| `improving_threshold` | `float` | `0.05` | Slope above which a metric trend is classified as "improving". |
| `declining_threshold` | `float` | `-0.05` | Slope below which a metric trend is classified as "declining". |
| `collaboration_weights` | `object` or `null` | `null` | Custom weights for collaboration scoring components. `null` uses defaults. |
| `llm_sampling_rate` | `float` | `0.01` | Fraction of task events sampled for LLM calibration. |
| `llm_sampling_model` | `string` or `null` | `null` | Model ID for LLM calibration sampling. `null` disables sampling. |
| `calibration_retention_days` | `int` | `90` | Days to retain calibration records before expiry. |

!!! note "Validation Rules"
    - `quality_ci_weight + quality_llm_weight` must equal `1.0` (tolerance: 1e-6)
    - `improving_threshold` must be strictly greater than `declining_threshold`
    - `quality_judge_provider` requires `quality_judge_model` to be set

## Structured Logging

Structured logging pipeline built on **structlog** + stdlib, with automatic sensitive field
redaction, async-safe correlation tracking, and per-domain log routing.

### Sink Layout

Eleven default sinks, activated at startup via `bootstrap_logging()`:

| Sink | Type | Level | Format | Routes | Description |
|------|------|-------|--------|--------|-------------|
| Console | stderr | INFO | Colored text | All loggers | Human-readable development output |
| `synthorg.log` | File | INFO | JSON | All loggers | Main application log (catch-all) |
| `audit.log` | File | INFO | JSON | `synthorg.security.*`, `synthorg.hr.*`, `synthorg.observability.*` | Audit-relevant events (security, HR, observability) |
| `errors.log` | File | ERROR | JSON | All loggers | Errors and above only |
| `agent_activity.log` | File | DEBUG | JSON | `synthorg.engine.*`, `synthorg.core.*`, `synthorg.communication.*`, `synthorg.tools.*`, `synthorg.memory.*` | Agent execution, communication, tools, and memory |
| `cost_usage.log` | File | INFO | JSON | `synthorg.budget.*`, `synthorg.providers.*` | Cost records and provider calls |
| `debug.log` | File | DEBUG | JSON | All loggers | Full debug trace (catch-all) |
| `access.log` | File | INFO | JSON | `synthorg.api.*` | HTTP request/response access log |
| `persistence.log` | File | INFO | JSON | `synthorg.persistence.*` | Database operations, migrations, CRUD |
| `configuration.log` | File | INFO | JSON | `synthorg.settings.*`, `synthorg.config.*` | Settings resolution, config loading |
| `backup.log` | File | INFO | JSON | `synthorg.backup.*` | Backup/restore lifecycle |

In addition to the 11 default sinks, three shipping sink types are available for centralized
log aggregation and telemetry export:

| Sink Type | Transport | Format | Description |
|-----------|-----------|--------|-------------|
| Syslog | UDP or TCP to a configurable endpoint | JSON | Ship structured logs to rsyslog, syslog-ng, or Graylog |
| HTTP | Batched POST to a configurable URL | JSON array | Ship log batches to any JSON-accepting endpoint |
| OTLP | HTTP POST to an OpenTelemetry collector | OTLP JSON | Map structlog events to OTLP log records with correlation IDs as trace context |

The HTTP sink sends raw JSON arrays.  Backends that expect different payload formats
(e.g., Grafana Loki's `/loki/api/v1/push`, Elasticsearch's `/_bulk`) require a
collector/proxy (Promtail, Logstash, Vector, etc.) to translate the payload.

Shipping sinks are catch-all (no logger name routing) and are configured at runtime via the
`custom_sinks` setting or YAML. See the [Centralized Logging](../guides/centralized-logging.md)
guide for configuration examples and deployment patterns.

Logger name routing is implemented via `_LoggerNameFilter` on file handlers. Sinks without
explicit routing are catch-all (accept all loggers at their configured level).

Exception formatting differs between sink types: `format_exc_info` is applied only to sinks
with `json_format=True` (converting `exc_info` tuples to formatted traceback strings for
serialization). Sinks with `json_format=False` (the default console sink) omit this
processor because `ConsoleRenderer` handles exception rendering natively.

### Log Directory

- **Docker**: `/data/logs/` (under the `synthorg-data` volume, persisted across restarts)
- **Local dev**: `logs/` relative to working directory (default)
- **Override**: `SYNTHORG_LOG_DIR` env var

### Rotation and Compression

File sinks use `RotatingFileHandler` by default (10 MB max, 5 backup files). Alternative:
`WatchedFileHandler` for external logrotate (`rotation.strategy: external` in config).

Rotated backup files can be automatically gzip-compressed by setting `compress_rotated: true`
in the rotation config. Compressed backups are stored as `.log.N.gz` instead of `.log.N`,
typically achieving 5--10x size reduction for structured JSON logs. Compression is off by
default for backward compatibility. `compress_rotated` is only supported with the builtin
rotation strategy; it is rejected when `rotation.strategy` is set to `external`.

### Sensitive Field Redaction

The `sanitize_sensitive_fields` processor automatically redacts values for keys matching:
`password`, `secret`, `token`, `api_key`, `api_secret`, `authorization`, `credential`,
`private_key`, `bearer`, `session`. Redaction applies at all nesting depths in structured
log events. Redacted values are replaced with `"**REDACTED**"`.

### Correlation Tracking

Three correlation IDs propagated via `contextvars` (async-safe):

- **`request_id`**: Bound per HTTP request by `RequestLoggingMiddleware`. Links all log
  events during a single API call.
- **`task_id`**: Bound per task execution. Links agent activity to a specific task.
- **`agent_id`**: Bound per agent execution context.

All three are automatically injected into every log event by `merge_contextvars` in the
structlog processor chain.

### Per-Logger Levels

Default levels per domain module (overridable via `LogConfig.logger_levels`):

| Logger | Default Level |
|--------|---------------|
| `synthorg.engine` | DEBUG |
| `synthorg.memory` | DEBUG |
| `synthorg.core` | INFO |
| `synthorg.communication` | INFO |
| `synthorg.providers` | INFO |
| `synthorg.budget` | INFO |
| `synthorg.security` | INFO |
| `synthorg.tools` | INFO |
| `synthorg.api` | INFO |
| `synthorg.cli` | INFO |
| `synthorg.config` | INFO |
| `synthorg.templates` | INFO |

### Event Taxonomy

64 domain-specific event constant modules under `observability/events/` (one per subsystem:
api, budget, risk_budget, reporting, blueprint, workflow_version, tool, git, engine, communication, security, etc.). Every log call uses a typed constant
(e.g., `API_REQUEST_STARTED`, `BUDGET_RECORD_ADDED`) for consistent, grep-friendly event
names. Format: `"<domain>.<noun>.<verb>"` (e.g., `"api.request.started"`).

### Uvicorn Integration

Uvicorn's default access logger is **disabled** (`access_log=False`, `log_config=None`).
HTTP access logging is handled by `RequestLoggingMiddleware`, which provides richer structured
fields (method, path, status_code, duration_ms, request_id) through structlog. Uvicorn's own
handlers are cleared by `_tame_third_party_loggers()` and its loggers (`uvicorn`,
`uvicorn.error`, `uvicorn.access`) are set to `WARNING` with `propagate = True` -- startup
INFO messages (e.g., "Uvicorn running on ...") are intentionally suppressed since the
application's own lifecycle logging provides equivalent structured events via structlog.
Warning and error messages still propagate through the structlog pipeline.

### Litestar Integration

Litestar's built-in logging configuration is **disabled** (`logging_config=None` in the
`Litestar()` constructor). Without this, Litestar reconfigures stdlib's root handler on
startup via `dictConfig()`, which triggers `_clearExistingHandlers` and destroys the structlog
file sink handlers attached by `_bootstrap_app_logging()`. The bootstrap call in `create_app`
runs before the Litestar constructor and sets up all 11 sinks; `logging_config=None` ensures
they survive.

### Third-Party Logger Taming

LiteLLM and its HTTP stack (httpx, httpcore) attach their own `StreamHandler` instances at
import time, producing duplicate output in Docker logs -- once via the library's own handler,
and once again via root propagation through the structlog sinks.

`_tame_third_party_loggers()` (called as step 7 of `configure_logging`, before per-logger level
overrides so explicit user settings take precedence) resolves this by:

- Suppressing LiteLLM's raw `print()` output via `litellm.set_verbose = False` and
  `litellm.suppress_debug_info = True` (applied only when `litellm` is already imported --
  avoids triggering LiteLLM's expensive import side-effects)
- Clearing all handlers from `LiteLLM`, `LiteLLM Router`, `LiteLLM Proxy`, `aiosqlite`,
  `httpcore`, `httpcore.http11`, `httpcore.connection`, `httpx`, `uvicorn`, `uvicorn.error`,
  `uvicorn.access`, `anyio`, `multipart`, `faker`, and `faker.factory` loggers
- Setting each to `WARNING` and `propagate = True` so warnings and errors still flow through
  the structlog pipeline

The provider and persistence layers already log meaningful events at appropriate levels via
their own structlog calls; the third-party loggers would otherwise add noisy DEBUG output
that duplicates or contradicts those structured events.

### Docker Logging

Two layers of log management:

1. **App-level** (structlog): 11 sinks (10 file + 1 console). File sinks use `RotatingFileHandler`
   (10 MB x 5) writing JSON to `/data/logs/`. Console sink writes colored text to stderr.
2. **Container-level** (Docker): `json-file` driver with 10 MB x 3 rotation on
   stdout/stderr. Captures console sink output and any uncaught stderr.

The layers are complementary -- app files provide structured, routed logs; Docker captures
the console stream for `docker logs` access.

### Runtime Settings

Four observability settings are runtime-editable via `SettingsService`:

- `root_log_level` (enum: debug/info/warning/error/critical) -- changes the root logger level
- `enable_correlation` (boolean) -- toggles correlation ID injection
- `sink_overrides` (JSON) -- per-sink overrides keyed by sink identifier (`__console__` for the
  console sink, file path for file sinks). Each value is an object with optional fields:
  `enabled` (bool), `level` (string), `json_format` (bool), `rotation` (object with `max_bytes`,
  `backup_count`, `strategy`, `compress_rotated` (builtin-only)). The console sink cannot be disabled
  (`enabled: false` is rejected).
- `custom_sinks` (JSON) -- additional sinks as a JSON array. Each entry may specify `sink_type`
  (`file`, `syslog`, `http`; defaults to `file`). File sinks require `file_path` and accept
  `level`, `json_format`, `rotation`, `routing_prefixes`. Syslog sinks require `syslog_host`
  and accept `syslog_port`, `syslog_facility`, `syslog_protocol`, `level`. HTTP sinks require
  `http_url` and accept `http_headers`, `http_batch_size`, `http_flush_interval_seconds`,
  `http_timeout_seconds`, `http_max_retries`, `level`.

Console sink level can also be overridden via `SYNTHORG_LOG_LEVEL` env var.

Changes take effect without restart -- the `ObservabilitySettingsSubscriber` rebuilds the entire
logging pipeline via `configure_logging()` (idempotent) when any of the four observability
settings change (`root_log_level`, `enable_correlation`, `sink_overrides`, or `custom_sinks`).
Custom sink file paths cannot collide with default sink paths (reserved even if disabled).

---

## See Also

- [Notifications](notifications.md) -- notification dispatcher and sinks
- [Design Overview](index.md) -- full index
