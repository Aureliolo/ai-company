#!/usr/bin/env bash
# cis-scan.sh -- CIS Docker Benchmark v1.6.0 compliance check
#
# Usage: scripts/cis-scan.sh <image-ref>
#
# Requires trivy on PATH (installed by trivy-action or manually).
# Exits 1 if trivy is not available (workflow uses continue-on-error: true).

set -euo pipefail

IMAGE_REF="${1:?Usage: cis-scan.sh <image-ref>}"

if ! command -v trivy >/dev/null 2>&1; then
  echo "::error::trivy not on PATH; CIS scan did not run"
  exit 1
fi

trivy image --compliance docker-cis-1.6.0 --format table "$IMAGE_REF"
