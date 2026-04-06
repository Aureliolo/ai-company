#!/usr/bin/env bash
# PreToolUse hook: block Bash commands that write files.
# Agents must use Write/Edit tools instead of cat, echo, tee, sed -i,
# python -c, heredocs, etc.
#
# Exit behavior:
#   - Non-writing commands: exit 0 (allow)
#   - File-writing commands: print JSON with reason, exit 2

set -euo pipefail

# Try to extract command from JSON stdin (OpenCode mode), or fail-closed if parsing fails
if ! COMMAND=$(jq -r '.tool_input.command // ""' 2>&1); then
    cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Failed to parse tool input JSON"
  }
}
ENDJSON
    exit 2
fi
if [[ -z "$COMMAND" ]]; then
    exit 0
fi

deny() {
    local reason="$1"
    cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "$reason"
  }
}
ENDJSON
    exit 2
}

# Heredocs anywhere in command: << EOF, << 'EOF', <<"EOF", <<\EOF, <<-EOF, <<-'PLAN_EOF'
if printf '%s\n' "$COMMAND" | grep -qE '<<-?\s*\\?'"'"'?"?[A-Za-z_]'; then
    deny "Do not use heredocs (<< EOF) to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
fi

# Output redirection: > file, >> file, > /path, > "./path", > file.txt
# Block ALL redirects to files (only allow fd redirects like >&2, 2>&1)
# This catches: echo > file.txt, cat > foo, > output, etc. (anywhere in command)
if printf '%s\n' "$COMMAND" | grep -qE '(^|[^|&;])\s*>>?\s*"?[^-]'; then
    # Extract redirect target to check if it's a file descriptor
    REDIR=$(printf '%s\n' "$COMMAND" | grep -oE '>>?\s*"?[^|&;<>]+' | head -1 | sed 's/^>>\?["'"'"']*//')
    # Only allow if it's a file descriptor (>&N or <&N format)
    FD_RE='^&[0-9]+$'
    if [[ ! "$REDIR" =~ $FD_RE ]]; then
        deny "Do not use shell redirects (> or >>) to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
    fi
fi

# echo/printf > filename.ext (catches echo "text" > file.txt)
if printf '%s\n' "$COMMAND" | grep -qE '\b(echo|printf)\b.*>\s*\S+\.\S+'; then
    deny "Do not use echo/printf with redirects to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
fi

# tee to files (not just piping through)
if printf '%s\n' "$COMMAND" | grep -qE '\btee\s+[^|]'; then
    deny "Do not use tee to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
fi

# sed -i (in-place editing)
if printf '%s\n' "$COMMAND" | grep -qE '\bsed\s+-i'; then
    deny "Do not use sed -i to edit files in place. Use the Edit tool to modify existing files. Never use Bash for file modification."
fi

# awk with output redirection
if printf '%s\n' "$COMMAND" | grep -qE '\bawk\b.*>\s*[^|&]'; then
    deny "Do not use awk with redirects to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
fi

# Python one-liners that write files
if printf '%s\n' "$COMMAND" | grep -qE 'python[23]?\s+-c\s.*\b(\.write|open\s*\()'; then
    deny "Do not use python -c to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
fi

exit 0
