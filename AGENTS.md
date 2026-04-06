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

## Memory Directory

When skills or agents reference "the project's auto memory directory", derive the path as:

```
~/.claude/projects/<mangled-cwd>/memory/
```

Where `<mangled-cwd>` is the project root path with path separators replaced by `--` (e.g., `C--Users-Aurelio-synthorg`). The `MEMORY.md` index in that directory is loaded via the global OpenCode config (`~/.config/opencode/opencode.json`).

Files use markdown with YAML frontmatter (`name`, `description`, `type`). Structure:
- **MEMORY.md**: Index with one-line pointers to memory files
- **research-log.md**: One-liner entries from `/research-link`
- **research/**: Detailed research write-ups
- **Individual memory files**: `user_*.md`, `feedback_*.md`, `project_*.md`, `reference_*.md`

## Shell Compatibility

This project runs on Windows. OpenCode uses PowerShell, Claude Code uses bash. When writing shell commands in skills:
- Use PowerShell-compatible syntax (e.g., `ls` not `ls -la`, `Select-String` not `grep`)
- Git commands work the same in both shells
- For bash-specific constructs (pipes, format strings), the model will self-correct to PowerShell equivalents

## OpenCode-Specific Notes

- **Model selection**: Use `/models` to switch between Ollama Cloud models
- **Plan mode**: Toggle with Tab (read-only exploration before execution)
- **Command palette**: Ctrl+P for quick access to commands
- **Session management**: Sessions persist in SQLite, resume with `--continue`
- **Skills**: Loaded from `.claude/skills/` (shared with Claude Code)
