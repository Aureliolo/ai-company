#!/usr/bin/env bash
# PreToolUse hook: gate Edit/Write during /pre-pr-review.
#
# The ``/pre-pr-review`` skill launches review agents in Phase 4 and is
# supposed to consolidate their findings into a triage table (Phase 5)
# then ask the user for approval (Phase 6) before implementing any fix
# (Phase 7). In practice, the agent (me, Claude) has a recurring
# failure mode: as async agent results arrive, it starts editing files
# immediately, skipping the triage-and-approval gate.
#
# This hook makes that failure structurally impossible. The skill
# creates ``.claude/pre-pr-review-active.lock`` before launching
# agents and removes it only after the user has approved the triage.
# While the lock exists, any ``Edit`` / ``Write`` call is rejected --
# except writes under ``_audit/`` so the skill can still publish the
# triage file and notes.
#
# Exit behavior:
#   - Lock missing: exit 0 (allow -- normal workflow, skill inactive)
#   - Lock present, target path under _audit/: exit 0 (allow triage writes)
#   - Lock present, target path is the lock itself: exit 0
#   - Lock present, any other target OR hook input is malformed:
#     print JSON + exit 2 (deny; fail closed so a bug in input
#     handling cannot accidentally let edits through)

set -euo pipefail

LOCK=".claude/pre-pr-review-active.lock"

if [[ ! -f "$LOCK" ]]; then
    exit 0
fi

# Fail-closed on malformed / missing input: if we cannot parse the hook
# payload (``jq`` unavailable or input not JSON) or extract a file
# path, deny rather than allow. The allowlist below is only reachable
# when we positively identified a path that matches an allowed
# segment.
if ! FILE_PATH=$(jq -r '.tool_input.file_path // ""' 2>/dev/null); then
    echo "triage gate: could not parse hook input via jq; failing closed" >&2
    FILE_PATH=""
fi

deny() {
    local why=$1
    echo "triage gate: $why; failing closed" >&2
    # Fall through to the JSON deny block below by exiting the
    # allowlist early.
    return 0
}

if [[ -z "$FILE_PATH" ]]; then
    deny "tool_input.file_path is empty or missing"
else
    # Canonicalise the path so segment-boundary checks cannot be
    # bypassed via ``..`` traversal. ``realpath -m`` does not require
    # the path to exist, which is correct for Edit/Write targets that
    # are about to be created. If canonicalisation fails we FAIL
    # CLOSED rather than fall back to the raw syntactic path --
    # otherwise ``_audit/../src/foo.py`` could slip through via the
    # embedded ``_audit`` segment.
    if CANONICAL=$(realpath -m "$FILE_PATH" 2>/dev/null); then
        NORMALISED="${CANONICAL//\\//}"

        # Segment-anchored allowlist. Bash regex ``=~`` matches
        # against forward-slash segment boundaries so ``/_audit/``
        # cannot be matched by an embedded substring inside a larger
        # path segment (e.g. ``/foo_audit_bar/``).
        if [[ "$NORMALISED" =~ (^|/)_audit(/|$) ]]; then
            exit 0
        fi

        # Allow writes to the lock file itself so the skill can
        # manage its own marker. Compare the canonical path against
        # the canonical lock path so only the exact lock location
        # (``.claude/pre-pr-review-active.lock`` relative to the
        # repo root) is permitted -- a basename-only check would
        # allow any file anywhere in the tree that happens to share
        # the lock's filename.
        if LOCK_CANONICAL=$(realpath -m "$LOCK" 2>/dev/null); then
            LOCK_NORMALISED="${LOCK_CANONICAL//\\//}"
            if [[ "$NORMALISED" == "$LOCK_NORMALISED" ]]; then
                exit 0
            fi
        fi
    else
        deny "realpath -m failed to canonicalise FILE_PATH; cannot safely apply allowlist"
    fi
fi

REASON=$(cat <<'REASON_END'
Blocked by /pre-pr-review triage gate.

The review agents have launched but the triage table has not yet been
presented to the user, or the user has not yet approved the fix list.

Required workflow:
  1. Wait for ALL review agents to complete.
  2. Write the consolidated triage table to _audit/pre-pr-review/triage.md.
  3. Call AskUserQuestion to confirm which findings to implement.
  4. On approval, remove .claude/pre-pr-review-active.lock.
  5. Then implement fixes.

If you believe you are NOT inside /pre-pr-review, remove the lock
manually: rm .claude/pre-pr-review-active.lock
REASON_END
)

# jq to safely JSON-escape the multi-line reason for the hook response.
ESCAPED=$(printf '%s' "$REASON" | jq -Rsa .)

cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": $ESCAPED
  }
}
ENDJSON
exit 2
