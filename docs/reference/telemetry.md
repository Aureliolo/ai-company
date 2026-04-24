# Telemetry (Product)

On-demand reference for product telemetry. The short rule in `CLAUDE.md` is: telemetry is opt-in and off by default; every event property must be explicitly allowlisted; never bypass the scrubber.

## Enabling

- Off by default. Enable with `SYNTHORG_TELEMETRY=true` or the `telemetry.enabled` setting.
- Delivery backend is Logfire; missing token or invalid extra config downgrades to the noop reporter silently.

## Privacy by allowlist

Every event property must be explicitly listed in `src/synthorg/telemetry/privacy.py::_ALLOWED_PROPERTIES` keyed by event type. Unknown keys raise `PrivacyViolationError` and are dropped before delivery.

Forbidden key patterns (rejected even if allowlisted):

- `key`, `token`, `secret`, `password`, `credential`, `bearer`, `auth`
- `content`, `message`, `prompt`, `description`

String values are capped at `synthorg.telemetry.config.MAX_STRING_LENGTH` (64 chars).

## Environment resolution chain

First match wins, implemented in `synthorg.telemetry.collector._resolve_environment`:

1. `SYNTHORG_TELEMETRY_ENV` (operator override; always wins).
2. CI auto-detection: `CI`, `GITLAB_CI`, `BUILDKITE`, `JENKINS_URL`, any `RUNPOD_*` → `"ci"`.
3. `SYNTHORG_TELEMETRY_ENV_BAKED` (Dockerfile `ARG DEPLOYMENT_ENV` baked at build; CI sets `prod` / `pre-release` / `dev`).
4. `TelemetryConfig.environment` (default `"dev"`).

## Docker daemon enrichment

At startup via `synthorg.telemetry.host_info.fetch_docker_info` (uses `aiodocker`). Requires `/var/run/docker.sock` bind-mounted (sandbox overlay / `synthorg init --sandbox true`).

Allowlisted fields:
`docker_server_version`, `docker_operating_system`, `docker_os_type`, `docker_os_version`, `docker_architecture`, `docker_kernel_version`, `docker_storage_driver`, `docker_default_runtime`, `docker_isolation`, `docker_ncpu`, `docker_mem_total`, `docker_gpu_runtime_nvidia_available`.

When the socket isn't mounted or the daemon is unreachable, the event carries `docker_info_available=False` + a categorical `docker_info_unavailable_reason`.

## Adding a new event or property

Keep in sync:

1. `host_info._extract()` (if sourcing from host info).
2. The `DockerHostInfo` TypedDict (if a Docker field).
3. The scrubber's `_ALLOWED_PROPERTIES` entry for the event type.

New allowlisted keys must not match a forbidden pattern. Never bypass the scrubber.
