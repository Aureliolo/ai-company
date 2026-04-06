---
description: Deep codebase audit with parallel specialized agents
---

# OpenCode Adapter (read this FIRST, before the skill below)

You are running in **OpenCode**, not Claude Code. Apply these overrides:

### Subagent spawning

The skill below uses the Claude Code `Agent` tool with `subagent_type` parameters. In OpenCode, spawn subagents using the agent definitions from `.opencode/agents/` directory. Load the agent's `.md` file as the subagent prompt and use the model specified in its frontmatter.

Agent type mapping (same as pre-pr-review/aurelio-review-pr):

| Skill references this | Use this OpenCode agent instead |
|---|---|
| `pr-review-toolkit:code-reviewer` | `.opencode/agents/code-reviewer.md` |
| `everything-claude-code:python-reviewer` | `.opencode/agents/python-reviewer.md` |
| `everything-claude-code:security-reviewer` | `.opencode/agents/security-reviewer.md` |
| `everything-claude-code:database-reviewer` | `.opencode/agents/persistence-reviewer.md` |
| `everything-claude-code:go-reviewer` | `.opencode/agents/go-reviewer.md` |

### GitHub issue creation

The skill uses `mcp__github__issue_write`. In OpenCode, use `gh issue create` via shell instead.

### Shell compatibility

This runs on Windows with PowerShell. Self-correct when bash syntax fails.

---

@.claude/skills/codebase-audit/SKILL.md

Arguments: $ARGUMENTS
