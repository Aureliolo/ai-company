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
# creates ``_audit/pre-pr-review-active.lock`` before launching agents
# and removes it only after the user has approved the triage. While
# the lock exists, any ``Edit`` / ``Write`` call is rejected -- except
# writes under ``_audit/`` so the skill can still publish the triage
# file and notes.
#
# Exit behavior:
#   - Lock missing: exit 0 (allow -- normal workflow, skill inactive)
#   - Lock present, target path under _audit/: exit 0 (allow triage writes)
#   - Lock present, any other target: print JSON + exit 2 (deny)

set -euo pipefail

LOCK=".claude/pre-pr-review-active.lock"

if [[ ! -f "$LOCK" ]]; then
    exit 0
fi

if ! FILE_PATH=$(jq -r '.tool_input.file_path // ""' 2>/dev/null); then
    exit 0
fi

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Normalise to forward slashes for pattern matching on any platform.
NORMALISED="${FILE_PATH//\\//}"

# Allow writes to the triage artifact directory so the skill can write
# the consolidated table and any per-agent notes.
if [[ "$NORMALISED" == *"/_audit/"* || "$NORMALISED" == "_audit/"* ]]; then
    exit 0
fi

# Allow writes to the lock itself so the skill can manage its own marker.
if [[ "$NORMALISED" == *"/$LOCK" || "$NORMALISED" == "$LOCK" ]]; then
    exit 0
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
