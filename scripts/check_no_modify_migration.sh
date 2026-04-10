#!/usr/bin/env bash
# Pre-commit hook: block commits that modify (not add) existing migration files.
# Migrations should be deleted and regenerated, not hand-edited.
#
# Bypass: set SYNTHORG_MIGRATION_SQUASH=1 when committing after a squash.
#
# Exit codes:
#   0 -- allow (no modified migrations, squash bypass, or only new ones)
#   1 -- blocked (existing migration was modified)

set -euo pipefail

if [ "${SYNTHORG_MIGRATION_SQUASH:-0}" = "1" ]; then
    exit 0
fi

REVISIONS_DIR="src/synthorg/persistence/sqlite/revisions"

mapfile -t MODIFIED < <(
    git diff --cached --name-only --diff-filter=M -- "$REVISIONS_DIR/*.sql" 2>/dev/null || true
)

if [ "${#MODIFIED[@]}" -gt 0 ] && [ -n "${MODIFIED[0]}" ]; then
    echo "" >&2
    echo "ERROR: Do not modify existing migration files. Delete and regenerate instead:" >&2
    echo "" >&2
    for f in "${MODIFIED[@]}"; do
        echo "  Modified: $f" >&2
    done
    echo "" >&2
    echo "To fix:" >&2
    echo "  1. Delete the migration: rm $f" >&2
    echo "  2. Remove its line from atlas.sum" >&2
    echo "  3. Regenerate: atlas migrate diff --env sqlite <name>" >&2
    echo "" >&2
    exit 1
fi

exit 0
