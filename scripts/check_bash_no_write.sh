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

# Strip double-quoted string contents before redirect checks so that >
# inside -m "..." commit messages, script excerpts, or other string
# arguments does not trigger false positives.  Intentionally simple:
# does not handle escaped quotes inside strings, which is fine for the
# shell commands we need to guard against.
COMMAND_FOR_REDIR=$(printf '%s\n' "$COMMAND" | sed 's/"[^"]*"/""/g')

# Output redirection: > file, >> file, > /path, > "./path", > file.txt
# Block ALL redirects to files (only allow fd redirects like >&2, 2>&1)
# This catches: echo > file.txt, cat > foo, > output, etc. (anywhere in command)
if printf '%s\n' "$COMMAND_FOR_REDIR" | grep -qE '(^|[^|&;])\s*>>?\s*"?[^-]'; then
    # Extract redirect target to check if it's a file descriptor
    # Extract redirect target.  grep returns 1 when there is no match (e.g.
    # ">&1" where & is excluded from [^|&;<>]+); || true prevents set -e from
    # exiting the script when extraction yields no output.
    REDIR=$(printf '%s\n' "$COMMAND_FOR_REDIR" | grep -oE '>>?\s*"?[^|&;<>]+' | head -1 | sed -E 's/^>>?\s*["'"'"']*//' || true)
    # Only deny if a non-empty target was extracted and it is not a file
    # descriptor.  Empty REDIR means the target was &N (fd redirect such as
    # 2>&1) whose & could not be captured; those are always safe.
    FD_RE='^&[0-9]+$'
    if [[ -n "$REDIR" && "$REDIR" != "/dev/null" && ! "$REDIR" =~ $FD_RE ]]; then
        deny "Do not use shell redirects (> or >>) to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
    fi
fi

# echo/printf > filename.ext (catches echo "text" > file.txt)
if printf '%s\n' "$COMMAND_FOR_REDIR" | grep -qE '\b(echo|printf)\b.*>\s*\S+\.\S+'; then
    deny "Do not use echo/printf with redirects to write files. Use the Write tool to create new files or the Edit tool to modify existing files. Never use Bash for file creation or modification."
fi

# tee to files (not just piping through)
if printf '%s\n' "$COMMAND_FOR_REDIR" | grep -qE '\btee\s+[^|]'; then
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
