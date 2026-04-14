#!/usr/bin/env bash
# PreToolUse hook: block Edit/Write on test timing baselines.
# Baseline files must only be updated with explicit user approval.
# Claude must never autonomously bump baselines to bypass regression guards.
#
# Protected files:
#   - tests/baselines/unit_timing.json
#   - tests/baselines/*.json (all baselines)
#
# Exit behavior:
#   - Non-baseline files: exit 0 (allow)
#   - Baseline files: print JSON with reason, exit 2

set -euo pipefail

if ! FILE_PATH=$(jq -r '.tool_input.file_path // ""' 2>/dev/null); then
    exit 0
fi
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

if [[ "$FILE_PATH" == */tests/baselines/*.json || "$FILE_PATH" == tests/baselines/*.json ]]; then
    REASON="Test timing baselines require explicit user approval to modify. Do not bump baselines to bypass regression guards -- fix the source code or tests instead."
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
