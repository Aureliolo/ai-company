# syntax=docker/dockerfile:1.10
# =============================================================================
# SynthOrg Sandbox -- thin wrapper over apko-composed Wolfi base
# =============================================================================
# The base image (ghcr.io/aureliolo/synthorg-sandbox-base) is composed
# declaratively by docker/sandbox/apko.yaml and published by CI.  It includes
# busybox, git, iptables, python-3.14, and nodejs-25 -- everything the
# sandbox-init.sh entrypoint needs for allowed_hosts enforcement (D16).
# =============================================================================

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="synthorg-sandbox" \
      org.opencontainers.image.description="SynthOrg agent code execution sandbox" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

COPY --chown=10001:10001 --chmod=755 docker/sandbox/sandbox-init.sh /usr/local/bin/sandbox-init

WORKDIR /workspace
USER 10001

HEALTHCHECK --interval=10s --timeout=3s --retries=2 --start-period=5s \
    CMD ["true"]

CMD ["sleep", "infinity"]
