#!/usr/bin/env bash
# check-git-c-cwd.sh
# PreToolUse hook: blocks `git -C <current-dir>` (pointless),
# allows `git -C <other-dir>` (legitimate cross-worktree ops).

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Not a git -C command -- no opinion
if [[ -z "$COMMAND" ]] || ! echo "$COMMAND" | grep -qE 'git[[:space:]]+-C[[:space:]]+'; then
    exit 0
fi

# Extract path after -C (handles quoted and unquoted)
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
    echo '{"decision":"block","reason":"BLOCKED: git -C points to the current working directory. Just use git directly -- the Bash tool already runs in the project root."}'
fi
