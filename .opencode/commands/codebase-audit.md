---
description: "Full codebase audit: launches 123 specialized agents to find issues across Python/React/Go/docs/website, writes findings to _audit/findings/, then triages with user"
---

# OpenCode Adapter (read this FIRST, before the skill below)

You are running in **OpenCode**, not Claude Code. Apply these overrides:

### Subagent spawning

The rewritten skill launches 123 audit agents with custom embedded prompts via the `Agent` tool. These are NOT mapped to `.opencode/agents/` -- they use inline prompts defined in the skill itself. Spawn each agent with its prompt from the skill's Agent Roster section.

### Scope changes

Supported scopes: `full`, `src/`, `web/`, `cli/`, `docs/`. The old scopes `.github/`, `ci`, `docker/`, `site/`, `src/synthorg/` are no longer valid.

### GitHub issue creation

The skill uses `mcp__github__issue_write`. In OpenCode, use `gh issue create` via shell instead.

### Shell compatibility

This runs on Windows with PowerShell. Self-correct when bash syntax fails. The `rm -rf _audit` setup command should use `Remove-Item -Recurse -Force _audit -ErrorAction SilentlyContinue`.

---

@.claude/skills/codebase-audit/SKILL.md

Arguments: $ARGUMENTS
