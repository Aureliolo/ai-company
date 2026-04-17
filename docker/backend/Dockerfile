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
# dedicated synthorg-fine-tune-gpu / -cpu images (large, torch inside);
# `telemetry` stays opt-in to avoid pulling logfire on default installs.
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
# download the static binary directly from Atlas's release CDN.
#
# URL tag choice:
#   Atlas publishes numbered tags (-v1.2.0) and a moving rebuild tag
#   (-latest). The community CDN only rebuilds `-latest` when upstream
#   ships Go stdlib security patches -- numbered tags stay frozen at
#   the Go version available on release day, including known-vulnerable
#   stdlib (e.g. v1.2.0 is built with Go 1.25.0, which carries several
#   HIGH/CRITICAL CVEs in crypto/tls and crypto/x509).
#
#   We therefore pin the URL to `-latest` but lock the per-arch SHA256
#   so builds are reproducible. Current rebuild: 2026-04-16, Atlas 1.2.0
#   + Go 1.25.9 (patched). Refresh both ATLAS_SHA256_* values with
#   `curl -sL <url> | sha256sum` whenever the upstream CDN publishes a
#   new rebuild; renovate's customManager on ariga/atlas GitHub
#   releases raises a reminder PR when upstream tags a new numbered
#   version (at which point we reassess whether to switch back to a
#   numbered URL once Atlas ships v1.3+).
# ---------------------------------------------------------------------------
FROM curlimages/curl:8.19.0@sha256:9a6f6a17667960e077f1b153009aaf18ac99a622221084e1938a45a06fff057a AS atlas

# renovate: datasource=github-releases depName=ariga/atlas
ARG ATLAS_VERSION=v1.2.0
ARG ATLAS_SHA256_AMD64=585830f49a84d7a30c49caa8e8145fd4fb07cc16952dce915f72d7e93f1ed9bc
ARG ATLAS_SHA256_ARM64=b1c50f55ae10054286ce4c20238c68168434f3275b5d2051841a926cf7fdd62a
ARG TARGETARCH

SHELL ["/bin/ash", "-o", "pipefail", "-c"]

# curlimages/curl runs as the non-root curl_user by default. Write the
# binary into the user's home (HOME=/home/curl_user) so we stay on the
# default USER and keep hadolint (DL3002: last USER must not be root)
# happy without adding a ignore directive -- the binary is moved to
# /usr/local/bin via COPY --from=atlas in the runtime stage below.
RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
        amd64) ATLAS_SHA256="${ATLAS_SHA256_AMD64}" ;; \
        arm64) ATLAS_SHA256="${ATLAS_SHA256_ARM64}" ;; \
        *) echo "Unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL --retry 3 \
        "https://release.ariga.io/atlas/atlas-community-linux-${TARGETARCH:-amd64}-latest" \
        -o /home/curl_user/atlas; \
    echo "${ATLAS_SHA256}  /home/curl_user/atlas" | sha256sum -c -; \
    chmod +x /home/curl_user/atlas; \
    # Alpine ldd on a static binary prints "Not a valid dynamic program"
    # (or similar) and exits non-zero. Treat an exit-zero ldd that lists
    # interpreter/libc deps as the failure case.
    if ldd /home/curl_user/atlas 2>/dev/null | grep -Eq 'ld-linux|libc\.so|=> /'; then \
        echo "ERROR: /atlas is dynamically linked; incompatible with the distroless runtime." >&2; \
        exit 1; \
    fi

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
# PATH set below (the Wolfi base image does not include
# /usr/local/bin by default, so the ENV PATH line prepends it
# explicitly).
COPY --from=atlas /home/curl_user/atlas /usr/local/bin/atlas

ENV PATH="/app/.venv/bin:/usr/local/bin:$PATH" \
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
