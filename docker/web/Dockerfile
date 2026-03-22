# syntax=docker/dockerfile:1

# =============================================================================
# SynthOrg Web -- Multi-stage build: Node builder → nginx runtime
# CIS hardening applied via compose.yml (no-new-privileges, drop caps, etc.)
# =============================================================================

# Stage 1: Build Vue dashboard (non-root for defense-in-depth)
FROM node:25-alpine@sha256:5209bcaca9836eb3448b650396213dbe9d9a34d31840c2ae1f206cb2986a8543 AS builder
RUN addgroup -S build && adduser -S build -G build && mkdir /app && chown build:build /app
WORKDIR /app
COPY --chown=build:build web/package.json web/package-lock.json ./
# Run npm ci as build user so node_modules (including .vite cache) is owned by
# the same user that runs the build -- avoids permission errors in Vite.
USER build
# --ignore-scripts: security hardening; safe for current pure-JS deps.
# If a future dep needs postinstall, add `npm rebuild <pkg>` after this step.
RUN npm ci --ignore-scripts
COPY --chown=build:build web/ ./
RUN npm run build \
    && find /app/dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' -o -name '*.json' \) -size +256c -exec gzip -9 -k {} \;

# Stage 2: Serve with nginx
FROM nginxinc/nginx-unprivileged:1.29.5-alpine@sha256:ccbac1a4c20a8b41c5dd1691bd91d63eda3b7989d643a33fd47841838519bfb9

LABEL org.opencontainers.image.title="synthorg-web" \
      org.opencontainers.image.description="SynthOrg web dashboard" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY web/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=builder /app/dist/ /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=5s \
    CMD ["wget", "--spider", "--quiet", "http://127.0.0.1:8080/"]
