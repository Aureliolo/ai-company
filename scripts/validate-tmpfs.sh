#!/usr/bin/env bash
# validate-tmpfs.sh -- Validate tmpfs allocations against actual usage
#
# Usage: scripts/validate-tmpfs.sh
#
# Requires running containers via docker compose (docker/compose.yml).
# Reports tmpfs usage for each service and warns if any mount exceeds 80%.
#
# Exit codes:
#   0  All tmpfs mounts are within safe limits
#   1  One or more tmpfs mounts exceed 80% usage

set -euo pipefail

THRESHOLD=80
FAILED=0

echo "== tmpfs Allocation Validation =="
echo ""

# Services and their expected tmpfs mounts
declare -A SERVICES=(
  ["synthorg-backend"]="/tmp"
  ["synthorg-web"]="/tmp /config/caddy /data/caddy"
  ["nats"]="/tmp"
)

for service in "${!SERVICES[@]}"; do
  container=$(docker ps --filter "name=${service}" --format '{{.ID}}' | head -1)
  if [ -z "$container" ]; then
    echo "[SKIP] ${service}: container not running"
    continue
  fi

  echo "[${service}]"
  for mount in ${SERVICES[$service]}; do
    # df output: Filesystem Size Used Available Use% Mounted
    df_line=$(docker exec "$container" df -h "$mount" 2>/dev/null | tail -1) || {
      echo "  ${mount}: unable to read (no df in image?)"
      continue
    }
    size=$(echo "$df_line" | awk '{print $2}')
    used=$(echo "$df_line" | awk '{print $3}')
    pct=$(echo "$df_line" | awk '{print $5}' | tr -d '%')

    if [ "$pct" -ge "$THRESHOLD" ]; then
      echo "  ${mount}: ${used}/${size} (${pct}%) -- WARNING: exceeds ${THRESHOLD}%"
      FAILED=1
    else
      echo "  ${mount}: ${used}/${size} (${pct}%) -- OK"
    fi
  done
  echo ""
done

if [ "$FAILED" -ne 0 ]; then
  echo "FAIL: One or more tmpfs mounts exceed ${THRESHOLD}% -- consider increasing allocation in compose.yml"
  exit 1
else
  echo "PASS: All tmpfs mounts within safe limits"
fi
