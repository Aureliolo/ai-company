#!/usr/bin/env bash
# Partial migration squash: at 100+ migrations, squash the oldest 50 into a
# checkpoint baseline while keeping the newest 50 as individual files.
#
# This preserves the upgrade path for users on older versions -- their applied
# migrations still exist as individual files above the checkpoint.
#
# Run manually during the release process:
#   bash scripts/squash_migrations.sh
#
# Override thresholds:
#   SQUASH_THRESHOLD=80 SQUASH_KEEP=40 bash scripts/squash_migrations.sh

set -euo pipefail

if ! command -v atlas &> /dev/null; then
    echo "Error: atlas CLI not found. Install from https://atlasgo.io/getting-started"
    exit 1
fi

MIGRATION_DIR="src/synthorg/persistence/sqlite/revisions"
THRESHOLD="${SQUASH_THRESHOLD:-100}"
KEEP="${SQUASH_KEEP:-50}"

if [ ! -d "$MIGRATION_DIR" ]; then
    echo "Error: Migration directory not found: $MIGRATION_DIR"
    exit 1
fi

mapfile -t ALL_MIGRATIONS < <(
    find "$MIGRATION_DIR" -maxdepth 1 -name '*.sql' -printf '%f\n' | sort
)
count=${#ALL_MIGRATIONS[@]}
echo "Migration count: $count (threshold: $THRESHOLD, keep newest: $KEEP)"

if [ "$count" -le "$THRESHOLD" ]; then
    echo "Below threshold -- no squashing needed."
    exit 0
fi

squash_count=$((count - KEEP))
if [ "$squash_count" -le 0 ]; then
    echo "Nothing to squash (count=$count, keep=$KEEP)."
    exit 0
fi

target_migration="${ALL_MIGRATIONS[$((squash_count - 1))]}"
target_version="${target_migration%.sql}"

echo "Squashing oldest $squash_count migrations (up to $target_migration)..."
echo "Keeping newest $KEEP migrations as individual files."
echo ""
atlas migrate squash --env sqlite --to "$target_version"
echo ""
echo "Done. Review the result, then commit with:"
echo "  SYNTHORG_MIGRATION_SQUASH=1 git commit -m 'chore: squash oldest $squash_count migrations'"
