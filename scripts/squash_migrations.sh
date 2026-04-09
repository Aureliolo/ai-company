#!/usr/bin/env bash
# Squash migrations when the count exceeds a threshold.
#
# Run manually during the release process:
#   bash scripts/squash_migrations.sh
#
# The threshold defaults to 20 and can be overridden:
#   SQUASH_THRESHOLD=10 bash scripts/squash_migrations.sh

set -euo pipefail

MIGRATION_DIR="src/synthorg/persistence/sqlite/revisions"
THRESHOLD="${SQUASH_THRESHOLD:-50}"

count=$(find "$MIGRATION_DIR" -maxdepth 1 -name '*.sql' | wc -l)
echo "Migration count: $count (threshold: $THRESHOLD)"

if [ "$count" -le "$THRESHOLD" ]; then
    echo "Below threshold -- no squashing needed."
    exit 0
fi

echo "Squashing migrations..."
atlas migrate squash --env sqlite
echo "Done. Review the result and commit."
