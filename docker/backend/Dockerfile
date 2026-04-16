# syntax=docker/dockerfile:1.23@sha256:2780b5c3bab67f1f76c781860de469442999ed1a0d7992a5efdf2cffc0e3d769
# =============================================================================
# SynthOrg Backend -- 2-stage build: builder -> apko-composed Wolfi runtime
# =============================================================================
# Stage 1 (builder): compile Python deps + fix venv symlink for Wolfi paths.
# Stage 2 (runtime): apko-composed distroless Wolfi base (no shell, no pkg
#   manager). CIS Docker Benchmark v1.6.0 compliant (hardening via compose.yml).
#
# The base image is composed declaratively by docker/backend/apko.yaml and
# published by CI. This Dockerfile layers the uv-built venv and app source on
# top. No setup stage needed -- the symlink fix is done in the builder itself.
# =============================================================================

ARG BASE_IMAGE

# ---------------------------------------------------------------------------
# Stage 1 -- Builder (ephemeral: compiles deps, fixes venv symlink)
# ---------------------------------------------------------------------------
FROM python:3.14.3-slim@sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.7@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN addgroup --gid 65532 --system build \
    && adduser --uid 65532 --system --ingroup build --home /home/build build \
    && mkdir /app && chown build:build /app

WORKDIR /app

COPY --chown=65532:65532 pyproject.toml uv.lock ./
USER build
# Install the `postgres` and `distributed` extras unconditionally: both
# are runtime-selectable via `synthorg init --persistence-backend` and
# `--bus-backend`, so the image must carry psycopg and nats-py whether
# or not the user has chosen them yet. `fine-tune` lives in the
# dedicated synthorg-fine-tune image (5GB pytorch); `telemetry` stays
# opt-in to avoid pulling logfire on default installs.
RUN --mount=type=cache,target=/home/build/.cache/uv,uid=65532,gid=65532 \
    uv sync --frozen --no-dev --no-install-project --extra postgres --extra distributed

RUN touch README.md
COPY --chown=65532:65532 src/ src/
RUN --mount=type=cache,target=/home/build/.cache/uv,uid=65532,gid=65532 \
    uv sync --frozen --no-dev --extra postgres --extra distributed

RUN find /app/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Strip cached wheels only. Keep *.dist-info so Syft and other SBOM tooling
# can detect actual installed Python packages (not just declared dependencies).
RUN find /app/.venv -type d -name 'wheels' -exec rm -rf {} + 2>/dev/null || true

# Point venv Python symlink at Wolfi's path (/usr/bin/python) instead of
# the builder's (/usr/local/bin/python3.14).  Creates a dangling symlink
# in the builder that resolves when COPY'd to the Wolfi runtime stage.
RUN rm -f /app/.venv/bin/python \
    && ln -s /usr/bin/python /app/.venv/bin/python

# Pre-create the data directory tree in the builder so COPY --chown can
# transfer it to the shell-less runtime stage with correct ownership.
# Switch back to root for creating /data, then re-chown to the build user.
USER root
RUN mkdir -p /data/logs /data/memory && chown -R 65532:65532 /data
USER build

# ---------------------------------------------------------------------------
# Atlas CLI: required by the Postgres backend's migrate() path. We
# download the static binary directly from Atlas's release CDN rather
# than basing a stage on arigaio/atlas:* because the Docker image tags
# are not consistently rebuilt when upstream ships Go stdlib security
# patches. Pinning to a versioned URL plus per-arch SHA256 keeps the
# build reproducible and renovate-trackable.
#
# Renovate bumps `ATLAS_VERSION` via the `github-releases` datasource
# (see `customManagers` in renovate.json) when ariga/atlas tags a new
# release. After that bump, update both ATLAS_SHA256_* values by
# running `curl -sL <url> | sha256sum` against the new versioned URLs
# and committing alongside the version bump. Go stdlib CVEs waived in
# .github/.trivyignore.yaml with a short expiration so they are
# auto-revisited when upstream ships v1.3.0.
# ---------------------------------------------------------------------------
FROM debian:13.2-slim@sha256:7e490910eea2861b9664577a96b54ce68ea3e02ce7f51d89cb0103a6f9c213e0 AS atlas

# renovate: datasource=github-releases depName=ariga/atlas
ARG ATLAS_VERSION=v1.2.0
ARG ATLAS_SHA256_AMD64=19a1f09eaa5469011d2cfb07cd8bdcaa5bb39fbf7c31bd63a60ba9d9aa7f562d
ARG ATLAS_SHA256_ARM64=8f7f89dd977a85ffe9be66fe157ce462a03036ef67a229ce8a39c3b1856e53f9
ARG TARGETARCH

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# DL3008: pinning apt package versions in a throwaway builder stage that
#         never ships to the final image adds maintenance cost without
#         security benefit -- the Atlas binary itself is pinned by
#         per-arch SHA256 below, which is the actual trust boundary.
# hadolint ignore=DL3008
RUN set -euo pipefail; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl file; \
    rm -rf /var/lib/apt/lists/*; \
    case "${TARGETARCH:-amd64}" in \
        amd64) ATLAS_SHA256="${ATLAS_SHA256_AMD64}" ;; \
        arm64) ATLAS_SHA256="${ATLAS_SHA256_ARM64}" ;; \
        *) echo "Unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL --retry 3 \
        "https://release.ariga.io/atlas/atlas-community-linux-${TARGETARCH:-amd64}-${ATLAS_VERSION}" \
        -o /atlas; \
    echo "${ATLAS_SHA256}  /atlas" | sha256sum -c -; \
    chmod +x /atlas; \
    if ldd /atlas 2>&1 | grep -Eq 'ld-linux|libc\.so|=> /'; then \
        echo "ERROR: /atlas is dynamically linked; incompatible with the distroless runtime." >&2; \
        exit 1; \
    fi; \
    file /atlas | grep -q "statically linked" || { \
        echo "ERROR: /atlas is not statically linked per file(1)." >&2; \
        exit 1; \
    }

# ---------------------------------------------------------------------------
# Stage 2 -- Runtime (apko-composed Wolfi base: no shell, no package manager)
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="synthorg-backend" \
      org.opencontainers.image.description="SynthOrg orchestration backend" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

WORKDIR /app

COPY --from=builder --chown=65532:65532 /app/.venv /app/.venv
COPY --from=builder --chown=65532:65532 /app/src /app/src
COPY --chown=65532:65532 pyproject.toml uv.lock /app/

# Pre-create the data directory with correct ownership so Docker
# initialises fresh volumes with uid/gid 65532 instead of root.
# COPY from builder stage because the distroless runtime has no shell.
COPY --from=builder --chown=65532:65532 /data /data

# Atlas CLI for postgres migration apply on startup. The binary is
# self-contained; copying it into /usr/local/bin places it on the
# default PATH without needing a shell or package manager in the
# distroless runtime.
COPY --from=atlas /atlas /usr/local/bin/atlas

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SYNTHORG_HOST="0.0.0.0" \
    SYNTHORG_PORT="3001" \
    UVICORN_HOST="0.0.0.0" \
    UVICORN_PORT="3001" \
    PYTHONWARNINGS="ignore::UserWarning:litestar.plugins.pydantic.utils"

USER 65532
EXPOSE 3001

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=30s \
    CMD ["/app/.venv/bin/python", "-c", "import json,urllib.request,sys,os; port=os.environ.get('UVICORN_PORT','3001'); r=urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health'); d=json.loads(r.read()); sys.exit(0 if d.get('data',{}).get('status')=='ok' else 1)"]

ENTRYPOINT []
CMD ["/app/.venv/bin/uvicorn", "synthorg.api.app:create_app", "--factory", "--no-access-log"]
