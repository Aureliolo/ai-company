#!/usr/bin/env bash
# evaluate-scan.sh -- Evaluate Trivy scan JSON results
#
# Usage: scripts/evaluate-scan.sh [--verbose] <trivy-json> <label>
#
#   --verbose   Render a vulnerability table and append to $GITHUB_STEP_SUMMARY
#   <trivy-json> Path to the Trivy JSON output file
#   <label>      Human-readable label (e.g. "Backend", "Sandbox Base")
#
# Exit codes:
#   0  No CRITICAL vulnerabilities found
#   1  CRITICAL vulnerabilities found, or missing input file
#
# HIGH vulnerabilities emit a GitHub Actions warning but do not fail the build.

set -euo pipefail

VERBOSE=0
if [ "${1:-}" = "--verbose" ]; then
  VERBOSE=1
  shift
fi

TRIVY_JSON="${1:?Usage: evaluate-scan.sh [--verbose] <trivy-json> <label>}"
LABEL="${2:?Usage: evaluate-scan.sh [--verbose] <trivy-json> <label>}"

if [ ! -f "$TRIVY_JSON" ]; then
  echo "::error::${TRIVY_JSON} not found -- Trivy scan may have failed to produce output"
  exit 1
fi

CRITICAL=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' "$TRIVY_JSON")
HIGH=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' "$TRIVY_JSON")

echo "## Trivy Scan -- ${LABEL}"
echo "Critical: ${CRITICAL}, High: ${HIGH}"

if [ "$VERBOSE" -eq 1 ]; then
  TOTAL=$(jq '[.Results[]?.Vulnerabilities[]?] | length' "$TRIVY_JSON")
  if [ "$TOTAL" -eq 0 ]; then
    echo "No CRITICAL or HIGH vulnerabilities found."
    echo "## Trivy Scan -- ${LABEL}: No CRITICAL or HIGH vulnerabilities found." >> "$GITHUB_STEP_SUMMARY"
  else
    TABLE=$(jq -r '
      ["SEVERITY","CVE","PACKAGE","VERSION","TITLE"],
      (.Results[]?.Vulnerabilities[]? |
        [.Severity, .VulnerabilityID, .PkgName, .InstalledVersion, (.Title // "")[0:60]]) |
      @tsv
    ' "$TRIVY_JSON" | column -t -s$'\t')
    echo "$TABLE"
    printf '## Trivy Scan -- %s\n```\n%s\n```\n' "$LABEL" "$TABLE" >> "$GITHUB_STEP_SUMMARY"
  fi
  echo "**Critical: ${CRITICAL}, High: ${HIGH}**" >> "$GITHUB_STEP_SUMMARY"
fi

if [ "$HIGH" -gt 0 ]; then
  echo "::warning::Found ${HIGH} HIGH severity vulnerabilities"
fi

if [ "$CRITICAL" -gt 0 ]; then
  echo "::error::Found ${CRITICAL} CRITICAL vulnerabilities -- failing build"
  exit 1
fi
