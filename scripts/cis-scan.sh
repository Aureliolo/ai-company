#!/usr/bin/env bash
# cis-scan.sh -- CIS Docker Benchmark v1.6.0 compliance check
#
# Usage: scripts/cis-scan.sh <image-ref>
#
# Requires trivy on PATH (installed by trivy-action or manually).
# Exits 1 if any CIS control has FAIL status.

set -uo pipefail

IMAGE_REF="${1:?Usage: cis-scan.sh <image-ref>}"

if ! command -v trivy >/dev/null 2>&1; then
  echo "::error::trivy not on PATH; CIS scan did not run"
  exit 1
fi

# Capture output without set -e so we always print results even if
# trivy itself exits non-zero (scan error, auth issue, etc.).
TRIVY_RC=0
OUTPUT=$(trivy image --compliance docker-cis-1.6.0 --format table "$IMAGE_REF" 2>&1) || TRIVY_RC=$?
echo "$OUTPUT"

if [ "$TRIVY_RC" -ne 0 ]; then
  echo "::error::trivy exited with code ${TRIVY_RC} -- see output above"
  exit 1
fi

if echo "$OUTPUT" | grep -q "| FAIL |"; then
  echo "::error::CIS Docker Benchmark found failures -- see table above"
  exit 1
fi
