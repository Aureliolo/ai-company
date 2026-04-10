#!/usr/bin/env bash
# Squash migrations when the count exceeds a threshold.
#
# Run manually during the release process:
#   bash scripts/squash_migrations.sh
#
# The threshold defaults to 50 and can be overridden:
#   SQUASH_THRESHOLD=30 bash scripts/squash_migrations.sh

set -euo pipefail

if ! command -v atlas &> /dev/null; then
    echo "Error: atlas CLI not found. Install from https://atlasgo.io/getting-started"
    exit 1
fi

MIGRATION_DIR="src/synthorg/persistence/sqlite/revisions"
THRESHOLD="${SQUASH_THRESHOLD:-50}"

if [ ! -d "$MIGRATION_DIR" ]; then
    echo "Error: Migration directory not found: $MIGRATION_DIR"
    exit 1
fi

count=$(find "$MIGRATION_DIR" -maxdepth 1 -name '*.sql' -printf '.' | wc -c)
echo "Migration count: $count (threshold: $THRESHOLD)"

if [ "$count" -le "$THRESHOLD" ]; then
    echo "Below threshold -- no squashing needed."
    exit 0
fi

echo "Squashing migrations..."
atlas migrate squash --env sqlite
echo ""
echo "Done. Review the result, then commit with:"
echo "  SYNTHORG_MIGRATION_SQUASH=1 git commit -m 'chore: squash migrations'"
