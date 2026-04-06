#!/usr/bin/env bash
# PreToolUse hook: block Bash commands that write files.
# Agents must use Write/Edit tools instead of cat, echo, tee, sed -i,
# python -c, heredocs, etc.
#
# Exit behavior:
#   - Non-writing commands: exit 0 (allow)
#   - File-writing commands: print JSON with reason, exit 2

set -euo pipefail

COMMAND=$(jq -r '.tool_input.command // ""' 2>/dev/null)

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

# Heredocs anywhere in command: << EOF, << 'EOF', <<-EOF, <<'PLAN_EOF'
if printf '%s\n' "$COMMAND" | grep -qE "<<-?\s*'?[A-Za-z_]"; then
    deny "Do not use heredocs (<< EOF) to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
fi

# Output redirection to a file: > file, >> file, > /path, > "./path"
# Skip >/dev/null, >&2, etc.
if printf '%s\n' "$COMMAND" | grep -qE '>\s*"?(/[^d>]|\.\.?/|[a-zA-Z]:\\)'; then
    deny "Do not use shell redirects (> or >>) to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
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
