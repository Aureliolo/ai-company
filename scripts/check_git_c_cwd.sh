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

# Robust token-based parsing: split command into tokens, find -C, capture next token
GIT_C_PATH=""
in_git=false
for token in $COMMAND; do
    if [[ "$token" == "git" ]]; then
        in_git=true
    elif [[ "$in_git" == true ]]; then
        if [[ "$token" == "-C" ]] || [[ "$token" == "--git-dir" ]]; then
            continue
        elif [[ "$token" == -* ]]; then
            # Skip other git options
            continue
        else
            # This is the path after -C
            GIT_C_PATH="$token"
            break
        fi
    fi
done

# If no path found after -C, fail open
if [[ -z "$GIT_C_PATH" ]]; then
    exit 0
fi

# Handle quoted paths
GIT_C_PATH="${GIT_C_PATH//\"/}"

# Canonicalize both paths using realpath (or readlink -f) for robust comparison
normalize() {
    local p="$1"
    # If realpath available, use it for absolute canonical paths
    if command -v realpath > /dev/null 2>&1; then
        p=$(realpath -e "$p" 2>/dev/null || echo "$p")
    fi
    # Also handle Windows-style paths as fallback
    p=$(echo "$p" | sed -E 's|^([A-Za-z]):[/\\]|/\L\1/|')
    p="${p//\\//}"
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
