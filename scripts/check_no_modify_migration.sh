#!/usr/bin/env bash
# Pre-commit hook: block commits that modify migration files that
# already exist on origin/main. Migrations are immutable once merged
# to main -- hand-editing them breaks Atlas's checksum chain for
# anyone who already ran them. Regeneration of a migration that was
# added earlier on the same PR branch (delete + `atlas migrate diff`)
# is an allowed workflow -- the net diff against main is still a
# single new file, so this script permits it.
#
# Exit codes:
#   0 -- allow (no migration touched, or only PR-local migrations changed)
#   1 -- blocked (a migration that exists on origin/main was modified)

set -euo pipefail

REVISIONS_DIRS=(
    "src/synthorg/persistence/sqlite/revisions"
    "src/synthorg/persistence/postgres/revisions"
)

# Resolve the baseline we compare against. We use the merge-base with
# origin/main so the check reflects the PR's net effect on main --
# not intermediate branch state. This lets agents delete + regenerate
# their own in-flight migrations without bypassing the check.
if ! git rev-parse --verify origin/main >/dev/null 2>&1; then
    # No origin/main available (detached, shallow clone, etc). Fail
    # open so we do not block legitimate work in unusual checkouts.
    exit 0
fi

BASE="$(git merge-base HEAD origin/main 2>/dev/null || true)"
if [ -z "$BASE" ]; then
    exit 0
fi

# Stage-aware comparison: diff the staged tree against the merge base,
# following renames so a delete+add with identical content is recognized
# as an add (not a modification).
STAGED_TREE="$(git write-tree)"

MODIFIED=()
for dir in "${REVISIONS_DIRS[@]}"; do
    while IFS= read -r line; do
        [ -n "$line" ] && MODIFIED+=("$line")
    done < <(
        git diff-tree -r --no-commit-id --name-only \
            --diff-filter=M --find-renames \
            "$BASE" "$STAGED_TREE" -- "$dir/*.sql" 2>/dev/null || true
    )
done

if [ "${#MODIFIED[@]}" -eq 0 ] || [ -z "${MODIFIED[0]}" ]; then
    exit 0
fi

echo "" >&2
echo "ERROR: Do not modify migration files that already exist on origin/main." >&2
echo "Migrations are immutable once merged -- Atlas checksum chains break for" >&2
echo "anyone who already ran them." >&2
echo "" >&2
for f in "${MODIFIED[@]}"; do
    echo "  Modified vs origin/main: $f" >&2
done
echo "" >&2
echo "If you need to change an already-merged migration:" >&2
echo "  1. Leave the existing migration alone." >&2
echo "  2. Create a NEW migration with your delta:" >&2
echo "       atlas migrate diff --env sqlite <name>" >&2
echo "" >&2
echo "If you are mid-PR regenerating a migration your own branch added," >&2
echo "this check will already pass (the file is not on origin/main yet)." >&2
echo "" >&2
exit 1
