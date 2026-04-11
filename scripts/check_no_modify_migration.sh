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

MODIFIED=()
while IFS= read -r line; do
    [ -n "$line" ] && MODIFIED+=("$line")
done < <(git diff --cached --name-only --diff-filter=MR -- "$REVISIONS_DIR/*.sql" 2>/dev/null || true)

if [ "${#MODIFIED[@]}" -gt 0 ] && [ -n "${MODIFIED[0]}" ]; then
    echo "" >&2
    echo "ERROR: Do not modify existing migration files. Delete and regenerate instead:" >&2
    echo "" >&2
    for f in "${MODIFIED[@]}"; do
        echo "  Modified: $f" >&2
    done
    echo "" >&2
    # Normalize BASE the same way as check_single_migration_per_pr.sh so
    # the echoed git restore command emits a valid remote-tracking ref.
    BASE_RAW="${BASE_BRANCH:-${GITHUB_BASE_REF:-origin/main}}"
    case "$BASE_RAW" in
        refs/remotes/*) BASE="${BASE_RAW#refs/remotes/}" ;;
        refs/heads/*)   BASE="origin/${BASE_RAW#refs/heads/}" ;;
        refs/*)         BASE="origin/${BASE_RAW#refs/}" ;;
        origin/*)       BASE="$BASE_RAW" ;;
        *)              BASE="origin/$BASE_RAW" ;;
    esac
    echo "To fix: restore atlas.sum from the base branch and regenerate:" >&2
    echo "  1. git restore --source='$BASE' -- '$REVISIONS_DIR/atlas.sum'" >&2
    echo "  2. Delete all PR migration files: rm '$REVISIONS_DIR/<migration>.sql'" >&2
    echo "  3. Regenerate: atlas migrate diff --env sqlite <name>" >&2
    echo "" >&2
    echo "Do NOT manually edit atlas.sum -- always restore from the base branch." >&2
    echo "" >&2
    exit 1
fi

exit 0
