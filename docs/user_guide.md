# User Guide

How to run SynthOrg.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

## Quick Start (CLI)

The recommended way to run SynthOrg is via the CLI:

```bash
# Install CLI (Linux/macOS)
curl -sSfL https://synthorg.io/get/install.sh | bash

# Set up and start
synthorg init     # Interactive setup wizard
synthorg start    # Verify + pull images + start containers
synthorg status   # Show container health and versions
```

`synthorg start` (and `synthorg update`) automatically verifies container image **cosign signatures** and **SLSA provenance** before pulling. If verification fails (e.g. in an air-gapped environment without access to Sigstore infrastructure), pass `--skip-verify` or set `SYNTHORG_SKIP_VERIFY=1`.

The web dashboard is at [http://localhost:3000](http://localhost:3000) (default port).

Other CLI commands: `synthorg stop`, `synthorg logs`, `synthorg update`, `synthorg doctor`, `synthorg uninstall`, `synthorg backup`, `synthorg setup`. When updating, the CLI re-launches itself after binary replacement so the remaining steps (compose refresh, image pull) use the new version. If the compose template has changed (new environment variables, hardening tweaks), the diff is shown for approval before applying.

## Quick Start (Docker Compose — manual)

For development or if you prefer manual Docker Compose:

```bash
git clone https://github.com/Aureliolo/synthorg
cd synthorg
cp docker/.env.example docker/.env
docker compose -f docker/compose.yml up -d
```

### Containers

| Container | Image | Description |
|-----------|-------|-------------|
| **backend** | `ghcr.io/aureliolo/synthorg` | Python API server (Litestar). 3-stage build, Chainguard distroless runtime (no shell), runs as non-root (UID 65532). |
| **web** | `ghcr.io/aureliolo/synthorg-web` | Nginx + Vue 3 dashboard (PrimeVue + Tailwind CSS). SPA routing, proxies API and WebSocket requests to backend. |

### Environment Variables

Configuration is in `docker/.env` (copy from `docker/.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SYNTHORG_JWT_SECRET` | *(auto-generated)* | JWT signing secret. Auto-generated and persisted on first run. Set explicitly only for multi-instance deployments. Must be >= 32 characters if set. |
| `SYNTHORG_DB_PATH` | `/data/synthorg.db` | SQLite database path (inside container). |
| `SYNTHORG_MEMORY_DIR` | `/data/memory` | Agent memory storage directory (inside container). |
| `SYNTHORG_PERSISTENCE_BACKEND` | `sqlite` | Persistence backend for operational data. |
| `SYNTHORG_MEMORY_BACKEND` | `mem0` | Memory backend for agent memory. |
| `BACKEND_PORT` | `8000` | Host port for the backend API. |
| `WEB_PORT` | `3000` | Host port for the web dashboard. |
| `DOCKER_HOST` | *(unset)* | Docker socket for agent code execution sandbox (optional). |

### First-Run Setup

After the containers are running, open the web dashboard at [http://localhost:3000](http://localhost:3000). On a fresh install, the **setup wizard** will appear automatically and guide you through:

1. **Create an admin account** -- set up the first admin (CEO) user.
2. **Configure an LLM provider** -- select a preset (Ollama, OpenRouter, etc.) or add a custom provider. Test the connection inline.
3. **Create your company** -- name your synthetic organization and optionally start from a template.
4. **Hire your first agent** -- choose a role, model, and personality for the first AI agent.

All four steps must be completed -- the backend validates that a company, at least one agent, and at least one provider exist before allowing setup to finish. After completing the wizard, the dashboard appears and the setup wizard is not shown again.

To re-run the wizard later, use `synthorg setup` (resets the flag and opens the browser) or delete the `api.setup_complete` setting via the settings API.

!!! info "Active Development"
    SynthOrg is under active development. The web dashboard is available for monitoring and managing the organization. Templates and some features described here may evolve. Check the [GitHub repository](https://github.com/Aureliolo/synthorg) for current status.

## Templates

Choose a pre-built organization template to get started quickly:

| Template | Description |
|----------|-------------|
| `startup` | CEO + small engineering team |
| `agency` | Project manager + specialists |
| `research-lab` | Lead researcher + research assistants |

Templates are selected through the dashboard. Full list coming soon.

## Stop

```bash
docker compose -f docker/compose.yml down
```

## Next Steps

- Templates — Full list of pre-built configurations (coming soon)
- REST API — Interact with your org via the API (coming soon)
- [Design Specification](design/index.md) — Full architecture details
