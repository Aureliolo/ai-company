#!/usr/bin/env bash
# PreToolUse hook: block git push if branch is behind origin/main.
# Reads Bash tool input from stdin JSON. If the command is a git push,
# fetches origin/main and checks if the branch needs rebasing.
#
# Exit behavior:
#   - Non-push commands: exit 0 (allow)
#   - Push on up-to-date branch: exit 0 (allow)
#   - Push on behind branch: print blocking JSON, exit 2

set -euo pipefail

# Extract the bash command from stdin JSON
COMMAND=$(jq -r '.tool_input.command // ""' 2>/dev/null)

# Only check git push commands (match anywhere for compound commands)
if ! printf '%s\n' "$COMMAND" | grep -qE '\bgit[[:space:]]+push\b'; then
    exit 0
fi

# Fetch latest origin/main (fail closed -- block push if fetch fails)
if ! git fetch origin main --quiet 2>/dev/null; then
    echo "Failed to fetch origin/main -- cannot verify branch is up to date. Push blocked."
    exit 1
fi

# Check how many commits behind origin/main (fail closed)
if ! BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null); then
    echo "Failed to run git rev-list -- cannot verify branch is up to date. Push blocked."
    exit 1
fi

if [ "$BEHIND" -gt 0 ]; then
    BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Branch '$BRANCH' is $BEHIND commits behind origin/main. Rebase first: git fetch origin main && git rebase origin/main"
  }
}
ENDJSON
    exit 2
fi

exit 0
