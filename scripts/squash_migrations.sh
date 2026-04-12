#!/usr/bin/env bash
# Partial migration squash: when migration count exceeds THRESHOLD (default
# 100), squash the oldest (count - KEEP) migrations into a checkpoint baseline
# while keeping the newest KEEP (default 50) as individual files.
#
# Both SQLite and Postgres backends are processed independently in a single
# invocation.  Each backend may have different migration counts; only backends
# that exceed the threshold are squashed.
#
# Uses Atlas "checkpoint" to create a DDL-only snapshot of the schema at the
# squash point.  The checkpoint file is placed chronologically between the last
# squashed migration and the first kept migration so Atlas applies it correctly:
# fresh databases apply the checkpoint + remaining files; existing databases
# that are past the squash point skip the checkpoint and continue normally.
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

BACKENDS=("sqlite" "postgres")
THRESHOLD="${SQUASH_THRESHOLD:-100}"
KEEP="${SQUASH_KEEP:-50}"

if ! [[ "$THRESHOLD" =~ ^[0-9]+$ ]]; then
    echo "Error: SQUASH_THRESHOLD must be a non-negative integer, got '$THRESHOLD'" >&2
    exit 1
fi
if ! [[ "$KEEP" =~ ^[0-9]+$ ]]; then
    echo "Error: SQUASH_KEEP must be a non-negative integer, got '$KEEP'" >&2
    exit 1
fi

any_failed=0
any_squashed=0

# Clean up temp directories on unexpected exit (set -e, signals).
_TMP_DIRS=()
cleanup() { for d in "${_TMP_DIRS[@]}"; do rm -rf "$d"; done; }
trap cleanup EXIT

for backend in "${BACKENDS[@]}"; do
    MIGRATION_DIR="src/synthorg/persistence/$backend/revisions"
    echo "=== $backend ==="

    if [ ! -d "$MIGRATION_DIR" ]; then
        echo "Error: Migration directory not found: $MIGRATION_DIR" >&2
        any_failed=1
        echo ""
        continue
    fi

    ALL_MIGRATIONS=()
    for f in "$MIGRATION_DIR"/*.sql; do
        [ -f "$f" ] && ALL_MIGRATIONS+=("$(basename "$f")")
    done
    sorted=()
    while IFS= read -r line; do
        sorted+=("$line")
    done < <(printf '%s\n' "${ALL_MIGRATIONS[@]}" | sort)
    ALL_MIGRATIONS=("${sorted[@]}")
    count=${#ALL_MIGRATIONS[@]}
    echo "Migration count: $count (threshold: $THRESHOLD, keep newest: $KEEP)"

    if [ "$count" -le "$THRESHOLD" ]; then
        echo "Below threshold -- no squashing needed."
        echo ""
        continue
    fi

    squash_count=$((count - KEEP))
    if [ "$squash_count" -le 0 ]; then
        echo "Nothing to squash (count=$count, keep=$KEEP)."
        echo ""
        continue
    fi

    # Timestamps of the boundary files (14-digit prefix).
    last_squashed="${ALL_MIGRATIONS[$((squash_count - 1))]}"
    last_squash_ts="${last_squashed:0:14}"
    first_kept="${ALL_MIGRATIONS[$squash_count]}"
    first_kept_ts="${first_kept:0:14}"

    # The checkpoint timestamp must sit between the last squashed
    # and the first kept file.  Validate there is room.
    cp_ts=$((last_squash_ts + 1))
    if [ "$cp_ts" -ge "$first_kept_ts" ]; then
        echo "Error: no timestamp room between $last_squash_ts and $first_kept_ts." >&2
        echo "Timestamps are consecutive seconds.  Wait until there is at" >&2
        echo "least a 2-second gap between the last squashed file and the" >&2
        echo "first kept file before squashing." >&2
        any_failed=1
        echo ""
        continue
    fi

    echo "Squashing oldest $squash_count migrations into a checkpoint..."
    echo "  Last squashed: $last_squashed"
    echo "  First kept:    $first_kept"
    echo "  Checkpoint ts: $cp_ts"
    echo ""

    # Determine dev-url for this backend.
    if [ "$backend" = "sqlite" ]; then
        DEV_URL="sqlite://file?mode=memory"
    else
        DEV_URL="${POSTGRES_DEV_URL:-docker://postgres/18/dev?search_path=public}"
    fi

    # 1. Copy files to squash into a temp directory.
    tmp_partial=$(mktemp -d)
    _TMP_DIRS+=("$tmp_partial")
    for ((i = 0; i < squash_count; i++)); do
        cp "$MIGRATION_DIR/${ALL_MIGRATIONS[$i]}" "$tmp_partial/"
    done
    atlas migrate hash --dir "file://$tmp_partial"

    # 2. Create checkpoint in the temp directory.
    if ! atlas migrate checkpoint --dev-url "$DEV_URL" --dir "file://$tmp_partial"; then
        echo "$backend: checkpoint creation FAILED." >&2
        rm -rf "$tmp_partial"
        any_failed=1
        echo ""
        continue
    fi

    # 3. Find the checkpoint file (the new .sql file) using an
    #    associative array for O(n) lookup instead of nested loops.
    declare -A original_set
    for ((i = 0; i < squash_count; i++)); do
        original_set["${ALL_MIGRATIONS[$i]}"]=1
    done

    cp_orig=""
    for f in "$tmp_partial"/*.sql; do
        fname="$(basename "$f")"
        if [[ -z "${original_set[$fname]:-}" ]]; then
            cp_orig="$fname"
            break
        fi
    done
    unset original_set

    if [ -z "$cp_orig" ]; then
        echo "$backend: could not identify checkpoint file." >&2
        rm -rf "$tmp_partial"
        any_failed=1
        echo ""
        continue
    fi

    # 4. Build the squashed directory: renamed checkpoint + remaining files.
    tmp_squashed=$(mktemp -d)
    _TMP_DIRS+=("$tmp_squashed")
    cp_name="${cp_ts}_checkpoint.sql"
    cp "$tmp_partial/$cp_orig" "$tmp_squashed/$cp_name"
    for ((i = squash_count; i < count; i++)); do
        cp "$MIGRATION_DIR/${ALL_MIGRATIONS[$i]}" "$tmp_squashed/"
    done
    atlas migrate hash --dir "file://$tmp_squashed"

    # 5. Replace the original directory contents.
    #    Remove old .sql files and atlas.sum, keep __init__.py and other
    #    non-migration files.
    for f in "$MIGRATION_DIR"/*.sql; do
        rm -f "$f"
    done
    rm -f "$MIGRATION_DIR/atlas.sum"
    cp "$tmp_squashed"/*.sql "$MIGRATION_DIR/"
    cp "$tmp_squashed/atlas.sum" "$MIGRATION_DIR/"

    rm -rf "$tmp_partial" "$tmp_squashed"
    any_squashed=1

    echo "$backend: squash complete."
    echo "  Removed $squash_count migration files."
    echo "  Created checkpoint: $cp_name"
    echo "  Remaining individual files: $KEEP"
    echo ""
done

if [ "$any_squashed" -eq 1 ]; then
    echo "Done. Review the result, then commit with:"
    echo "  SYNTHORG_MIGRATION_SQUASH=1 git commit -m 'chore: squash oldest migrations'"
fi

exit "$any_failed"
