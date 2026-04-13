# syntax=docker/dockerfile:1.10
# =============================================================================
# SynthOrg Sandbox -- thin wrapper over apko-composed Wolfi base
# =============================================================================
# The base image (ghcr.io/aureliolo/synthorg-sandbox-base) is composed
# declaratively by docker/sandbox/apko.yaml and published by CI.  It includes
# busybox, git, python-3.14, and nodejs-25.  Network enforcement is handled
# by the sidecar proxy container (docker/sidecar/), not by the sandbox.
# =============================================================================

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="synthorg-sandbox" \
      org.opencontainers.image.description="SynthOrg agent code execution sandbox" \
      org.opencontainers.image.url="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.source="https://github.com/Aureliolo/synthorg" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.opencontainers.image.vendor="Aureliolo"

WORKDIR /workspace
USER 10001

CMD ["sleep", "infinity"]
