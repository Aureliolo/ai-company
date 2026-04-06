# AGENTS.md -- SynthOrg (OpenCode)

This project uses a shared configuration for both Claude Code and OpenCode.

**All project conventions, commands, and standards are defined in [CLAUDE.md](CLAUDE.md).**

Read CLAUDE.md for:
- Project structure, package layout, code conventions
- Quick commands (uv, pytest, ruff, mypy, docker, docs)
- Git workflow, commit conventions, branch naming
- Testing standards, coverage requirements
- Design spec (docs/design/) -- MANDATORY reading before implementation
- Logging, resilience, security patterns

## OpenCode-Specific Notes

- **Model selection**: Use `/models` to switch between Ollama Cloud models
- **Plan mode**: Toggle with Tab (read-only exploration before execution)
- **Command palette**: Ctrl+P for quick access to commands
- **Session management**: Sessions persist in SQLite, resume with `--continue`
- **Skills**: Loaded from `.claude/skills/` (shared with Claude Code)
