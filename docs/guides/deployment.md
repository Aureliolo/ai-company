---
title: Deployment (Docker)
description: Run SynthOrg in production with Docker, hardening, and image verification.
---

# Deployment (Docker)

SynthOrg runs as two Docker containers -- a Python backend API and a Caddy + React web dashboard. This guide covers production deployment, environment configuration, security hardening, and operations.

---

## Architecture

```mermaid
graph LR
    User["Browser"]
    Web["web<br/><small>caddy:8080</small><br/><small>UID 65532</small>"]
    Backend["backend<br/><small>uvicorn:3001</small><br/><small>UID 65532</small>"]
    Volume["synthorg-data<br/><small>SQLite + Memory</small>"]

    User -->|":3000"| Web
    Web -->|"/api/* proxy"| Backend
    Web -->|"/api/v1/ws proxy"| Backend
    Backend --> Volume
```

| Container | Image | Purpose |
|-----------|-------|---------|
| **backend** | `ghcr.io/aureliolo/synthorg-backend` | Litestar API server (Wolfi apko-composed distroless, non-root) |
| **web** | `ghcr.io/aureliolo/synthorg-web` | Caddy + React 19 SPA (proxies API and WebSocket) |

---

## Quick Deploy

=== "CLI (recommended)"

    ```bash
    synthorg init     # interactive setup wizard
    synthorg start    # pull images, verify signatures, start containers
    synthorg status   # verify health
    ```

=== "Docker Compose (manual)"

    ```bash
    git clone https://github.com/Aureliolo/synthorg
    cd synthorg
    cp docker/.env.example docker/.env
    # Edit docker/.env with your secrets (see Environment Variables below)
    docker compose -f docker/compose.yml up -d
    ```

See the [Quickstart Tutorial](quickstart.md) for a complete walkthrough and the [User Guide](../user_guide.md) for all CLI commands.

---

## Environment Variables

All environment variables are configured in `docker/.env` (copy from `docker/.env.example`):

### Required

| Variable | Description |
|----------|-------------|
| `SYNTHORG_JWT_SECRET` | JWT signing secret. Must be >= 32 characters of URL-safe base64. Never commit to version control. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SYNTHORG_SETTINGS_KEY` | Fernet encryption key for sensitive settings at rest. Must be a valid Fernet key. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `SYNTHORG_DB_PATH` | `/data/synthorg.db` | SQLite database path (inside container) |
| `SYNTHORG_MEMORY_DIR` | `/data/memory` | Agent memory storage directory |
| `SYNTHORG_PERSISTENCE_BACKEND` | `sqlite` | Persistence backend |
| `SYNTHORG_MEMORY_BACKEND` | `mem0` | Memory backend |
| `SYNTHORG_LOG_DIR` | `/data/logs` | Log file directory |
| `SYNTHORG_LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warning`, `error`, `critical` |
| `BACKEND_PORT` | `3001` | Host port for the backend API |
| `WEB_PORT` | `3000` | Host port for the web dashboard |
| `MEM0_TELEMETRY` | `false` | Mem0 telemetry (disable to reduce overhead) |
| `DOCKER_HOST` | *(unset)* | Docker socket for agent code execution sandbox (optional) |

---

## First-Run Setup

After the containers are running, open `http://localhost:3000`. The setup wizard appears on a fresh install. See the [User Guide](../user_guide.md#first-run-setup) for the full wizard walkthrough.

---

## Container Details

### Backend

- **Base image**: Wolfi apko-composed distroless (no shell, continuously scanned)
- **Build**: 2-stage (builder -> apko runtime) for minimal attack surface
- **User**: UID 65532 (distroless non-root)
- **Health check**: `GET /api/v1/health` (10s interval, 5s timeout, 3 retries, 30s start period)
- **Entry point**: `uvicorn synthorg.api.app:create_app --factory --no-access-log`

### Web

- **Base image**: Pure apko Wolfi (Caddy + melange-packaged static assets, no Dockerfile)
- **User**: UID 65532 (caddy)
- **Health check**: none (stateless static server; container readiness determined by TCP port availability)
- **Routing**: SPA routing (`try_files {path} /index.html`), API proxy to backend, WebSocket proxy, per-request CSP nonce via Caddy `templates` directive
- **Caching**: `/index.html` is no-cache; `/assets/*` is immutable with 1-year max-age (content-hashed filenames)
- **Static compression**: pre-compressed `.gz` files served via `file_server { precompressed gzip }`

---

## Security Hardening

The Docker Compose configuration follows the [CIS Docker Benchmark v1.6.0](https://www.cisecurity.org/benchmark/docker):

| Control | Setting | CIS Reference |
|---------|---------|---------------|
| No new privileges | `security_opt: [no-new-privileges:true]` | 5.3 |
| Drop all capabilities | `cap_drop: [ALL]` | 5.12 |
| Read-only root filesystem | `read_only: true` + tmpfs mounts | 5.25 |
| PID limits | 256 (backend), 64 (web) | 5.28 |
| Memory limits | 4G (backend), 256M (web) | -- |
| CPU limits | 2.0 (backend), 0.5 (web) | -- |
| Log rotation | json-file, 10MB max, 3 files | -- |
| Tmpfs security | `noexec,nosuid,nodev` on `/tmp` | -- |

### Security Headers (Caddy)

The web container sets the following response headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), camera=(), microphone=()`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'nonce-{http.request.uuid}' 'unsafe-inline'; style-src-elem 'self' 'nonce-{http.request.uuid}'; style-src-attr 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
- `Strict-Transport-Security: max-age=63072000` (2 years)

The CSP uses Level 3 directive splitting: `style-src-elem` locks `<style>` elements to the per-request nonce (injected by Caddy's `templates` directive substituting `{http.request.uuid}` into `<meta name="csp-nonce">`), while `style-src-attr 'unsafe-inline'` covers the transient inline positioning styles set by Floating UI (used internally by Base UI). See [`docs/security.md` → CSP Nonce Infrastructure](../security.md#csp-nonce-infrastructure) for the full flow -- any reverse proxy in front of the web container must preserve Caddy's template substitution and the matching CSP header, otherwise inline styles will be blocked.

---

## Volumes & Data Persistence

The `synthorg-data` Docker volume persists all application data:

- SQLite database (`/data/synthorg.db`)
- Agent memory files (`/data/memory/`)
- Log files (`/data/logs/`)

### Backup

```bash
synthorg backup             # create a backup
synthorg backup --list       # list available backups
synthorg backup --restore    # restore from backup
```

For manual Docker Compose deployments, back up the `synthorg-data` volume directly.

### Wipe & Reset

```bash
synthorg wipe    # offers backup, wipes all data, optionally restarts fresh
```

---

## Networking

Both containers run on the `synthorg-net` Docker network. The web container proxies API requests to the backend:

- `http://localhost:3000/api/*` -> `http://backend:3001/api/*`
- `ws://localhost:3000/api/v1/ws` -> `ws://backend:3001/api/v1/ws`

### Local LLM Providers

To use a local LLM like Ollama running on the host machine, configure the provider with `host.docker.internal`:

```yaml
providers:
  local-ollama:
    auth_type: none
    base_url: "http://host.docker.internal:11434"
```

---

## Image Verification

SynthOrg container images are signed with [cosign](https://docs.sigstore.dev/cosign/) keyless signatures and include [SLSA Level 3](https://slsa.dev/) provenance attestations.

`synthorg start` and `synthorg update` automatically verify signatures before pulling images. If verification fails (e.g. in an air-gapped environment):

```bash
synthorg start --skip-verify
# or
export SYNTHORG_SKIP_VERIFY=1
synthorg start
```

---

## Updates

```bash
synthorg update    # pull latest images, verify signatures, restart containers
```

The CLI re-launches itself after binary replacement so the remaining steps use the new version. If the compose template has structural changes, the diff is shown for approval before applying.

### Channels

| Channel | Description |
|---------|-------------|
| `stable` | Stable releases only (default) |
| `dev` | Pre-release builds on every push to main |

```bash
synthorg config set channel dev      # opt in to pre-release builds
synthorg config set channel stable   # switch back to stable
```

### Auto-Cleanup

Automatically remove old container images after updates (keeps current + previous version):

```bash
synthorg config set auto_cleanup true
```

---

## Production Checklist

!!! info "Production readiness checklist"

    - [ ] Generate strong secrets for `SYNTHORG_JWT_SECRET` and `SYNTHORG_SETTINGS_KEY`
    - [ ] Set `SYNTHORG_LOG_LEVEL` to `warning` or `info` (not `debug`)
    - [ ] Review and set appropriate `BACKEND_PORT` and `WEB_PORT`
    - [ ] Configure budget limits to prevent runaway LLM costs
    - [ ] Set autonomy level to `semi` or `supervised` (not `full`) for production orgs
    - [ ] Enable security audit logging (`security.audit_enabled: true`)
    - [ ] Set up backup schedule (`synthorg backup`)
    - [ ] Place behind a reverse proxy with TLS termination
    - [ ] Restrict Docker socket access if using the sandbox feature
    - [ ] Monitor container health via `synthorg status` or Docker health checks

---

## Troubleshooting

### Health Check

```bash
synthorg doctor    # run diagnostics
synthorg status    # check container health
synthorg logs      # view container logs
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Backend container keeps restarting | Check `synthorg logs` for startup errors. Verify `SYNTHORG_JWT_SECRET` and `SYNTHORG_SETTINGS_KEY` are set. |
| Dashboard shows "Connection refused" | Ensure the web container is healthy and `WEB_PORT` is not in use. |
| Image pull fails | Check network connectivity. If air-gapped, use `--skip-verify`. |
| "Port already in use" | Change `BACKEND_PORT` or `WEB_PORT` in `docker/.env`. |
| Ollama not connecting | Use `http://host.docker.internal:11434` as the base URL. |

---

## See Also

- [Quickstart Tutorial](quickstart.md) -- get started in 5 minutes
- [User Guide](../user_guide.md) -- CLI commands and setup wizard
- [Security](../security.md) -- security architecture reference
- [Company Configuration](company-config.md) -- full configuration reference
