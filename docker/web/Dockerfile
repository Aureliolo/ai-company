# syntax=docker/dockerfile:1

# =============================================================================
# SynthOrg Web -- Multi-stage build: Node builder + docs builder -> nginx runtime
# CIS hardening applied via compose.yml (no-new-privileges, drop caps, etc.)
# =============================================================================

# Stage 1: Build React dashboard (non-root for defense-in-depth)
FROM node:25-alpine@sha256:ad82ecad30371c43f4057aaa4800a8ed88f9446553a2d21323710c7b937177fc AS builder
RUN addgroup -S build && adduser -S build -G build && mkdir /app && chown build:build /app
WORKDIR /app
COPY --chown=build:build web/package.json web/package-lock.json web/.npmrc ./
# Run npm ci as build user so node_modules (including .vite cache) is owned by
# the same user that runs the build -- avoids permission errors in Vite.
USER build
# --ignore-scripts: security hardening; safe for current pure-JS deps.
# If a future dep needs postinstall, add `npm rebuild <pkg>` after this step.
RUN npm ci --ignore-scripts
COPY --chown=build:build web/ ./
RUN npm run build \
    && find /app/dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' -o -name '*.json' \) -size +256c -exec gzip -9 -k {} \;

# Stage 2: Build MkDocs documentation (non-root for defense-in-depth)
FROM python:3.14.3-slim@sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b AS docs-builder

COPY --from=ghcr.io/astral-sh/uv:0.10.9@sha256:10902f58a1606787602f303954cea099626a4adb02acbac4c69920fe9d278f82 /uv /uvx /bin/

RUN groupadd -r --gid 1001 docsbuild && useradd -r --uid 1001 -g docsbuild docsbuild \
    && mkdir /app && chown docsbuild:docsbuild /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

# Install dependencies first (layer cache -- only invalidated on lock change)
COPY --chown=docsbuild:docsbuild pyproject.toml uv.lock ./
USER docsbuild
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1001,gid=1001 \
    uv sync --frozen --group docs --no-dev --no-install-project

# Install project (export_openapi.py imports synthorg.api.app)
RUN touch README.md
COPY --chown=docsbuild:docsbuild src/ src/
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1001,gid=1001 \
    uv sync --frozen --group docs --no-dev

# Build documentation
COPY --chown=docsbuild:docsbuild docs/ docs/
COPY --chown=docsbuild:docsbuild mkdocs.yml ./
COPY --chown=docsbuild:docsbuild scripts/export_openapi.py scripts/
RUN uv run python scripts/export_openapi.py \
    && uv run zensical build

# Pre-compress docs output (match React builder pattern -- nginx has gzip_static on)
RUN find /app/_site/docs -type f \
    \( -name '*.html' -o -name '*.js' -o -name '*.css' \
       -o -name '*.svg' -o -name '*.json' -o -name '*.xml' \) \
    -size +256c -exec gzip -9 -k {} \;

# Stage 3: Serve with nginx
FROM nginxinc/nginx-unprivileged:1.29.5-alpine@sha256:601c823234c474696ded03d619e67f1e59538802731543099c691aea67e4a553

LABEL org.opencontainers.image.title="synthorg-web" \
      org.opencontainers.image.description="SynthOrg web dashboard" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY web/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=builder /app/dist/ /usr/share/nginx/html/
COPY --from=docs-builder /app/_site/docs/ /usr/share/nginx/html/docs/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=5s \
    CMD ["wget", "--spider", "--quiet", "http://127.0.0.1:8080/"]
