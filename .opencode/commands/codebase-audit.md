---
description: "Full codebase audit: launches 152 specialized agents to find issues across Python/React/Go/docs/website, writes findings to _audit/latest/findings/, then triages with user"
---

# OpenCode Adapter (read this FIRST, before the skill below)

You are running in **OpenCode**, not Claude Code. Apply these overrides:

### Subagent spawning

The rewritten skill launches 152 audit agents with custom embedded prompts via the `Agent` tool. These are NOT mapped to `.opencode/agents/` -- they use inline prompts defined in the skill itself. Spawn each agent with its prompt from the skill's Agent Roster section.

### Scope changes

Supported scopes: `full`, `src/`, `web/`, `cli/`, `docs/`. The old scopes `.github/`, `ci`, `docker/`, `site/`, `src/synthorg/` are no longer valid.

### GitHub issue creation

The skill uses `mcp__github__issue_write`. In OpenCode, use `gh issue create` via shell instead.

### Shell compatibility

This runs on Windows with PowerShell. Self-correct when bash syntax fails.

The new run-history layout (`_audit/runs/<date>/` plus `_audit/latest` symlink) needs PowerShell substitutes for the bash setup commands:

- `mkdir -p _audit/runs/<date>/findings` -> `New-Item -ItemType Directory -Force -Path _audit/runs/<date>/findings`
- `ln -sfn runs/<date> _audit/latest` -> `New-Item -ItemType SymbolicLink -Force -Path _audit/latest -Target runs/<date>` (requires Developer Mode on Windows or running as admin; if symlink creation fails, fall back to writing the run directory path into `_audit/latest.txt`)

---

@.claude/skills/codebase-audit/SKILL.md

Arguments: $ARGUMENTS
