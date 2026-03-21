FROM node:25-slim@sha256:44bcbf493408a824104e74976ae5539f596c46cbe75ed0423a137552a555e2de AS node-base

FROM python:3.14.3-slim@sha256:fb83750094b46fd6b8adaa80f66e2302ecbe45d513f6cece637a841e1025b4ca

LABEL org.opencontainers.image.title="synthorg-sandbox" \
      org.opencontainers.image.description="SynthOrg agent code execution sandbox" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules

# git version tracks base image; updated via Dependabot base image bumps.
# Symlink npm, install git + iptables, create sandbox user -- single layer.
# iptables is needed for allowed_hosts network enforcement via sandbox-init.
# hadolint ignore=DL3008
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update && apt-get install -y --no-install-recommends git iptables \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox `# IMPORTANT: UID must match setpriv --reuid in docker/sandbox/sandbox-init.sh` \
    && mkdir -p /workspace \
    && chown sandbox:sandbox /workspace

# Entrypoint for allowed_hosts enforcement (iptables + privilege drop).
# Only activated via container config override; default USER remains sandbox.
COPY --chmod=755 docker/sandbox/sandbox-init.sh /usr/local/bin/sandbox-init

WORKDIR /workspace

USER sandbox

HEALTHCHECK --interval=30s --timeout=3s --retries=2 \
  CMD ["true"]

CMD ["sleep", "infinity"]
