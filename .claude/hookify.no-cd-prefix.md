---
name: no-cd-prefix
enabled: true
event: bash
pattern: ^\s*cd\s+
action: block
---

**BLOCKED: Do not use `cd` in Bash commands -- it poisons the cwd for all subsequent calls.**

The working directory is ALREADY set to the project root. Run commands directly.

- WRONG: `cd <project-root> && git status` -- use `git status`
- WRONG: `cd cli && go test ./...` -- use `go -C cli test ./...`
- WRONG: `cd <worktree-path> && uv run ruff check` -- use `uv run ruff check`

For Go commands: use `go -C cli <command>` (changes dir internally, no cwd side effects).
For subdir tools without a `-C`/`--prefix` equivalent: use `bash -c "cd <dir> && <cmd>"` -- runs in a child process, no cwd side effects.
- Go lint: `bash -c "cd cli && golangci-lint run"`
- npm install (bare, `--prefix` is broken for no-argument `npm install`): `bash -c "cd web && npm install"`
