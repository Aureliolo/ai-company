# syntax=docker/dockerfile:1

# =============================================================================
# SynthOrg Backend — Multi-stage, CIS-hardened container
# =============================================================================
# Three stages: builder → setup → runtime (distroless).
# Chainguard Python distroless: minimal attack surface (no shell, no package
# manager), non-root by default (UID 65532), continuously rebuilt by Chainguard.
# CIS Docker Benchmark v1.6.0 compliant.
# All base images pinned by version or digest (Dependabot auto-updates).
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — Builder (ephemeral: compiles deps + project wheel)
# ---------------------------------------------------------------------------
FROM python:3.14.3-slim@sha256:584e89d31009a79ae4d9e3ab2fba078524a6c0921cb2711d05e8bb5f628fc9b9 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.9@sha256:10902f58a1606787602f303954cea099626a4adb02acbac4c69920fe9d278f82 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN addgroup --gid 10000 --system build \
    && adduser --uid 10000 --system --ingroup build --home /home/build build \
    && mkdir /app && chown build:build /app

WORKDIR /app

# Install dependencies first (layer cache — only invalidated on lock change)
COPY --chown=build:build pyproject.toml uv.lock ./
USER build
RUN --mount=type=cache,target=/home/build/.cache/uv,uid=10000,gid=10000 \
    uv sync --frozen --no-dev --no-install-project

# Copy source and install project.
# touch README.md: hatchling requires README.md for package metadata but
# .dockerignore excludes it — create an empty file to satisfy the build.
RUN touch README.md
COPY --chown=build:build src/ src/
RUN --mount=type=cache,target=/home/build/.cache/uv,uid=10000,gid=10000 \
    uv sync --frozen --no-dev

# Strip __pycache__ from source (bytecode already compiled by uv into .venv)
RUN find /app/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ---------------------------------------------------------------------------
# Stage 2 — Setup (ephemeral: fix symlinks + create dirs, needs shell)
# ---------------------------------------------------------------------------
# Chainguard Python -dev variant (has shell for RUN commands).
# Pinned by digest — free tier only exposes latest/latest-dev tags.
# To update: docker buildx imagetools inspect cgr.dev/chainguard/python:latest-dev
FROM cgr.dev/chainguard/python@sha256:4decc0a7de3d586bbb38307244f32a10f50c96627714ac2785a347a8b63ceeb4 AS setup

USER root
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Fix venv Python symlink (builder points to /usr/local/bin/python3,
# Chainguard is /usr/bin/python), create data dir, set ownership.
RUN rm -f /app/.venv/bin/python && ln -s /usr/bin/python /app/.venv/bin/python \
    && mkdir -p /data && chown 65532:65532 /data \
    && chown -R 65532:65532 /app

# Drop root after setup — all stages must end as non-root
USER 65532

# ---------------------------------------------------------------------------
# Stage 3 — Runtime (distroless: no shell, no uv, no package manager)
# ---------------------------------------------------------------------------
# Chainguard Python distroless — minimal attack surface, continuously scanned.
# Pinned by digest — free tier only exposes latest/latest-dev tags.
# To update: docker buildx imagetools inspect cgr.dev/chainguard/python:latest
FROM cgr.dev/chainguard/python@sha256:308d2fda1d9ad9620454de97cb84fa407bd20e24dd66902909f4b3b44b310836 AS runtime

# OCI image labels (https://github.com/opencontainers/image-spec/blob/main/annotations.md)
LABEL org.opencontainers.image.title="synthorg-backend" \
      org.opencontainers.image.description="SynthOrg orchestration backend" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

WORKDIR /app

# Copy prepared venv, source, and data dir from setup stage
COPY --from=setup --chown=65532:65532 /app/.venv /app/.venv
COPY --from=setup --chown=65532:65532 /app/src /app/src
COPY --from=setup --chown=65532:65532 /data /data

# Runtime environment
# UVICORN_HOST / UVICORN_PORT control the server bind address (read natively
# by uvicorn via its Click auto_envvar_prefix). SYNTHORG_HOST / SYNTHORG_PORT
# are application-level config — they do NOT control uvicorn directly.
# When running standalone (`docker run`), override UVICORN_* to change the
# listening address. compose.yml bridges SYNTHORG_* → UVICORN_* automatically.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SYNTHORG_HOST="0.0.0.0" \
    SYNTHORG_PORT="8000" \
    UVICORN_HOST="0.0.0.0" \
    UVICORN_PORT="8000"

USER 65532

EXPOSE 8000

# Healthcheck — exec form (no shell needed, works with distroless)
# Reads UVICORN_PORT so the check stays valid if the port is overridden.
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=30s \
    CMD ["/usr/bin/python", "-c", "import json,urllib.request,sys,os; port=os.environ.get('UVICORN_PORT','8000'); r=urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health'); d=json.loads(r.read()); sys.exit(0 if d.get('data',{}).get('status')=='ok' else 1)"]

# Reset Chainguard base entrypoint (/usr/bin/python) so CMD runs uvicorn
# directly instead of being passed as Python arguments.
# Exec form (no shell) — works with distroless. Uvicorn reads UVICORN_HOST
# and UVICORN_PORT env vars natively; compose bridges SYNTHORG_* to these.
ENTRYPOINT []
CMD ["/app/.venv/bin/uvicorn", "synthorg.api.app:create_app", "--factory"]
