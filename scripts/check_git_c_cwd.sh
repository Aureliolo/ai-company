#!/usr/bin/env bash
# check-git-c-cwd.sh
# PreToolUse/pre-push hook: blocks `git -C <current-dir>` (pointless),
# allows `git -C <other-dir>` (legitimate cross-worktree ops).
# Works in two modes:
#   1. With JSON stdin from OpenCode: extracts command and checks
#   2. Without stdin (pre-commit): always passes (not applicable)

set -euo pipefail

# Try to extract command from JSON stdin (OpenCode mode), or skip check if no stdin
if ! COMMAND=$(jq -r '.tool_input.command // empty' 2>/dev/null); then
    exit 0
fi

# Not a git -C command -- no opinion
if [[ -z "$COMMAND" ]] || ! echo "$COMMAND" | grep -qE 'git[[:space:]]+-C[[:space:]]+'; then
    exit 0
fi

# Extract path after -C (handles quoted and unquoted)
# Note: this simple sed may miss cases where options appear between git and -C
# (e.g., git --no-pager -C path). For such cases, the script intentionally fails open.
GIT_C_PATH=$(echo "$COMMAND" | sed -E 's/.*git[[:space:]]+-C[[:space:]]+("([^"]+)"|([^[:space:]]+)).*/\2\3/')
GIT_C_PATH="${GIT_C_PATH//\"/}"

normalize() {
    local p="$1"
    # C:\ or C:/ -> /c/
    p=$(echo "$p" | sed -E 's|^([A-Za-z]):[/\\]|/\L\1/|')
    # backslashes -> forward slashes
    p="${p//\\//}"
    # trailing slash
    p="${p%/}"
    echo "$p"
}

NORM_ARG=$(normalize "$GIT_C_PATH")
NORM_PWD=$(normalize "$PWD")

if [[ "$NORM_ARG" == "$NORM_PWD" ]]; then
    cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: git -C points to the current working directory. Just use git directly -- the Bash tool already runs in the project root."
  }
}
ENDJSON
    exit 2
fi
