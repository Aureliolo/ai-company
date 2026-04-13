#!/usr/bin/env bash
# report-image-size.sh -- Report Docker image size to stdout and step summary
#
# Usage: scripts/report-image-size.sh <image-ref> <label>
#
# Outputs the image size in MB and appends a summary line to
# $GITHUB_STEP_SUMMARY (when the variable is set).

set -euo pipefail

IMAGE_REF="${1:?Usage: report-image-size.sh <image-ref> <label>}"
LABEL="${2:?Usage: report-image-size.sh <image-ref> <label>}"

SIZE_BYTES=$(docker image inspect --format='{{.Size}}' "$IMAGE_REF")
SIZE_MB=$(awk -v bytes="$SIZE_BYTES" 'BEGIN {printf "%.1f", bytes / 1048576}')

echo "Image size (${LABEL}): ${SIZE_MB} MB"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  echo "### ${LABEL}: ${SIZE_MB} MB" >> "$GITHUB_STEP_SUMMARY"
fi
