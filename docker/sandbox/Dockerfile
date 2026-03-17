FROM node:25-slim@sha256:44bcbf493408a824104e74976ae5539f596c46cbe75ed0423a137552a555e2de AS node-base

FROM python:3.14.3-slim@sha256:584e89d31009a79ae4d9e3ab2fba078524a6c0921cb2711d05e8bb5f628fc9b9

LABEL org.opencontainers.image.title="synthorg-sandbox" \
      org.opencontainers.image.description="SynthOrg agent code execution sandbox" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules

# git version tracks base image; updated via Dependabot base image bumps.
# Symlink npm, install git, create sandbox user — single layer.
# hadolint ignore=DL3008
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update && apt-get install -y --no-install-recommends git \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox \
    && mkdir -p /workspace \
    && chown sandbox:sandbox /workspace

WORKDIR /workspace

USER sandbox

HEALTHCHECK --interval=30s --timeout=3s --retries=2 \
  CMD ["true"]

CMD ["sleep", "infinity"]
