#!/usr/bin/env bash
# PreToolUse hook: block `atlas migrate hash` commands.
# Rehashing rewrites atlas.sum checksums. Post-release, this would silently
# invalidate existing database installations.
#
# If the migration needs to change, delete and regenerate:
#   1. Delete the in-progress migration .sql file
#   2. atlas migrate diff --env sqlite <name>
#
# Exit behavior:
#   - Non-rehash commands: exit 0 (allow)
#   - atlas migrate hash: print JSON with reason, exit 2

set -euo pipefail

if ! COMMAND=$(jq -r '.tool_input.command // ""' 2>/dev/null); then
    exit 0
fi
if [[ -z "$COMMAND" ]]; then
    exit 0
fi

if [[ "$COMMAND" =~ atlas[[:space:]]+migrate[[:space:]]+hash ]]; then
    REASON="Do not rehash Atlas migrations. Delete the migration and regenerate: atlas migrate diff --env sqlite <name>"
    cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "$REASON"
  }
}
ENDJSON
    exit 2
fi

exit 0
