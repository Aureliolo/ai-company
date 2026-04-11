#!/usr/bin/env bash
# Enforce: at most one new Atlas migration file per PR.
#
# Rationale: during a feature PR we want a clean schema history -- if the
# developer iterates on the schema multiple times they should delete the
# in-progress migration and regenerate it (the "delete-and-regenerate"
# workflow), so that the final PR ships exactly one migration. Multiple
# migrations per PR make review harder and pollute the release history.
#
# Algorithm:
#   1. Ensure origin/main is fetched.
#   2. Count new `.sql` files added under src/synthorg/persistence/sqlite/revisions/
#      on HEAD that do not exist on origin/main.
#   3. Fail if the count is greater than 1.
#
# The script runs on every commit (pre-commit stage) and every push (pre-push
# stage). On the `main` branch itself the check is skipped (main never adds
# its own migrations outside of a squashed PR).
#
# Exit codes:
#   0 -- allow (0 or 1 new migrations)
#   1 -- error (fetch failed or other unrecoverable condition)
#   2 -- blocked (more than one new migration)

set -euo pipefail

BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [ "$BRANCH" = "main" ]; then
    exit 0
fi

REVISIONS_DIR="src/synthorg/persistence/sqlite/revisions"

# Resolve the PR base branch. Precedence: BASE_BRANCH > GITHUB_BASE_REF >
# origin/main. CI sets GITHUB_BASE_REF to a bare branch name; local callers
# may set BASE_BRANCH to anything (bare, origin/<name>, or refs/heads/<name>).
BASE_RAW="${BASE_BRANCH:-${GITHUB_BASE_REF:-origin/main}}"

# Normalize to (1) a remote-tracking ref for comparisons with
# git cat-file / git show-ref, and (2) a bare branch name for git fetch.
case "$BASE_RAW" in
    refs/heads/*)       BASE_NAME="${BASE_RAW#refs/heads/}" ;;
    refs/remotes/*)     BASE_NAME="${BASE_RAW#refs/remotes/origin/}" ;;
    origin/*)           BASE_NAME="${BASE_RAW#origin/}" ;;
    refs/*)             BASE_NAME="${BASE_RAW#refs/}" ;;
    *)                  BASE_NAME="$BASE_RAW" ;;
esac
BASE="origin/$BASE_NAME"
FETCH_TARGET="$BASE_NAME"

# Ensure the base ref exists locally; only fetch as a fallback.
if ! git show-ref --verify --quiet "refs/remotes/$BASE_NAME" \
    && ! git rev-parse --verify --quiet "$BASE" >/dev/null; then
    if ! git fetch origin "$FETCH_TARGET" --quiet 2>/dev/null; then
        # In CI a missing base branch is a hard failure; locally it's a skip.
        if [ -n "${GITHUB_BASE_REF:-}" ]; then
            echo "check_single_migration_per_pr: CI base branch $BASE is unavailable; cannot validate migrations." >&2
            exit 1
        fi
        echo "check_single_migration_per_pr: $BASE is unavailable; skipping local check." >&2
        exit 0
    fi
fi

# Find all .sql files under revisions/ (staged + committed).
HEAD_FILES=()
while IFS= read -r line; do
    HEAD_FILES+=("$line")
done < <(git ls-files --cached -- "$REVISIONS_DIR/*.sql" 2>/dev/null || true)

# For each file on HEAD, check whether it exists on the base branch. If it
# does not, it is a new migration added by this PR.
NEW_COUNT=0
NEW_FILES=()
for f in "${HEAD_FILES[@]}"; do
    if ! git cat-file -e "${BASE}:${f}" 2>/dev/null; then
        NEW_COUNT=$((NEW_COUNT + 1))
        NEW_FILES+=("$f")
    fi
done

if [ "$NEW_COUNT" -gt 1 ]; then
    echo "" >&2
    echo "ERROR: This PR adds $NEW_COUNT new Atlas migration files, but the policy" >&2
    echo "allows at most ONE new migration per PR." >&2
    echo "" >&2
    echo "New migrations detected:" >&2
    for f in "${NEW_FILES[@]}"; do
        echo "  - $f" >&2
    done
    echo "" >&2
    echo "To fix: restore atlas.sum from the base branch, delete all PR" >&2
    echo "migration files, then regenerate a single consolidated migration:" >&2
    echo "" >&2
    echo "  1. git restore --source=$BASE -- $REVISIONS_DIR/atlas.sum" >&2
    echo "  2. rm $REVISIONS_DIR/<all_pr_migration_files>.sql" >&2
    echo "  3. atlas migrate diff --env sqlite <name>" >&2
    echo "" >&2
    echo "Do NOT manually edit atlas.sum -- always restore from the base branch." >&2
    exit 2
fi

exit 0
