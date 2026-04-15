# syntax=docker/dockerfile:1.23@sha256:2780b5c3bab67f1f76c781860de469442999ed1a0d7992a5efdf2cffc0e3d769
# =============================================================================
# SynthOrg Fine-Tune -- 2-stage build: builder -> apko-composed Wolfi runtime
# =============================================================================
# Stage 1 (builder): install torch + sentence-transformers + synthorg
#   fine-tune modules into a venv.
# Stage 2 (runtime): apko-composed Wolfi base with BLAS/math libs.
#
# This image is large (~4GB) due to PyTorch. It is only built when
# docker/fine-tune/** or src/synthorg/memory/embedding/fine_tune*.py
# changes, or on release tags.
# =============================================================================

ARG BASE_IMAGE

# ---------------------------------------------------------------------------
# Stage 1 -- Builder (installs ML deps + synthorg fine-tune code)
# ---------------------------------------------------------------------------
FROM python:3.14.3-slim@sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.6@sha256:b1e699368d24c57cda93c338a57a8c5a119009ba809305cc8e86986d4a006754 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN addgroup --gid 10003 --system fine-tune \
    && adduser --uid 10003 --system --ingroup fine-tune --home /home/fine-tune fine-tune \
    && mkdir /app && chown fine-tune:fine-tune /app

WORKDIR /app

COPY --chown=10003:10003 pyproject.toml uv.lock ./
USER fine-tune
RUN --mount=type=cache,target=/home/fine-tune/.cache/uv,uid=10003,gid=10003 \
    uv sync --frozen --no-dev --no-install-project --group fine-tune

RUN touch README.md
COPY --chown=10003:10003 src/ src/
RUN --mount=type=cache,target=/home/fine-tune/.cache/uv,uid=10003,gid=10003 \
    uv sync --frozen --no-dev --group fine-tune

RUN find /app/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find /app/.venv -type d -name 'wheels' -exec rm -rf {} + 2>/dev/null || true

# Point venv Python symlink at Wolfi's path (/usr/bin/python).
RUN rm -f /app/.venv/bin/python \
    && ln -s /usr/bin/python /app/.venv/bin/python

# ---------------------------------------------------------------------------
# Stage 2 -- Runtime (apko-composed Wolfi base)
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="synthorg-fine-tune" \
      org.opencontainers.image.description="SynthOrg embedding fine-tuning pipeline" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

WORKDIR /app

COPY --from=builder --chown=10003:10003 /app/.venv /app/.venv
COPY --from=builder --chown=10003:10003 /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10003

# No network exposure -- fine-tuning is a batch job.
# Config is mounted at /etc/fine-tune/config.json by the orchestrator.
# Source data is mounted at /data (read-only).
# Checkpoints written to /checkpoints (read-write).

# The runner starts an HTTP health server on port 15002.
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=30s \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:15002/healthz',timeout=2); sys.exit(0 if r.status==200 else 1)"]

ENTRYPOINT ["/app/.venv/bin/python", "-m", "synthorg.memory.embedding.fine_tune_runner"]
