#!/usr/bin/env bash
# cis-scan.sh -- CIS Docker Benchmark v1.6.0 compliance check
#
# Usage: scripts/cis-scan.sh <image-ref>
#
# Requires trivy on PATH (installed by trivy-action or manually).
# Exits 0 gracefully if trivy is not available.

set -euo pipefail

IMAGE_REF="${1:?Usage: cis-scan.sh <image-ref>}"

if ! command -v trivy >/dev/null 2>&1; then
  echo "::warning::trivy not on PATH, skipping CIS scan"
  exit 0
fi

trivy image --compliance docker-cis-1.6.0 --format table "$IMAGE_REF"
