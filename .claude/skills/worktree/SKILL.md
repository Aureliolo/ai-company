---
description: "Manage parallel worktrees: create with prompts, cleanup after merge, tree view, status"
argument-hint: "<setup|cleanup|status|tree|rebase> [options]"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - AskUserQuestion
---

# Worktree Manager

Manage parallel git worktrees for multi-issue development across phases. Handles creation, settings propagation, prompt generation, cleanup after merge, milestone tree view, and status overview.

**Arguments:** "$ARGUMENTS"

---

## Command: `setup`

Create worktrees, copy settings, and generate Claude Code prompts.

### Input formats (3 modes, from most to least explicit)

**Mode 1 — Full explicit:**
```
/worktree setup
feat/delegation-loop-prevention #12,#17 "Delegation + Loop Prevention"
feat/parallel-execution #22 "Parallel Agent Execution"
```

**Mode 2 — Shorthand (issues + description only):**
```
/worktree setup
#12,#17 "Delegation + Loop Prevention"
#22 "Parallel Execution"
```
Branch names auto-generated from description: `feat/delegation-loop-prevention`.

**Mode 3 — Milestone-aware:**
```
/worktree setup --milestone M4 --issues #26,#30,#133,#168
```
Fetches issue titles from GitHub, groups by the user's worktree definitions (or asks for grouping via AskUserQuestion if not provided).

If no definitions are provided at all, ask the user via AskUserQuestion for:
1. How many worktrees to create
2. For each: issues and description (branch names auto-generated)

### Directory naming

Directory suffix is auto-derived from the branch name:
- `feat/delegation-loop-prevention` → `../ai-company-wt-delegation-loop-prevention`
- Strip the `feat/`, `fix/`, `refactor/` etc. prefix, prepend `wt-`
- Repo name extracted from the current working directory basename

### Steps

1. **Pre-flight checks:**

   a. Ensure on main and up to date:
   ```bash
   git checkout main && git pull
   ```

   b. Check for uncommitted changes:
   ```bash
   git status --short
   ```
   If dirty, warn and ask via AskUserQuestion whether to proceed or abort.

   c. For each worktree definition, verify:
   - Branch doesn't already exist: `git branch --list <branch-name>`
   - Directory doesn't already exist: `test -d <dir-path>`
   If either exists, warn and ask how to proceed (skip / reuse / abort).

2. **Check `.claude/` local files exist:**

   ```bash
   ls .claude/settings.local.json 2>/dev/null
   ```

   If missing, warn: "No .claude/settings.local.json found — worktrees will prompt for tool permissions." Continue anyway.

3. **For each worktree definition**, run in sequence:

   a. Determine the directory path: `../<repo-name>-wt-<slug>` (e.g. `../ai-company-wt-delegation-loop-prevention`)

   b. Create the worktree:
   ```bash
   git worktree add -b <branch-name> <dir-path> main
   ```

   c. Copy all `.claude/` local files (settings, hooks, etc.):
   ```bash
   cp .claude/settings.local.json <dir-path>/.claude/settings.local.json
   ```
   Also copy any other `.claude/*.local.*` files if they exist:
   ```bash
   for f in .claude/*.local.*; do test -f "$f" && cp "$f" "<dir-path>/.claude/$(basename $f)"; done
   ```

4. **Verify all worktrees created:**

   ```bash
   git worktree list
   ```

5. **For each worktree, generate a Claude Code prompt.** The prompt must follow this exact structure:

   a. Fetch each issue's full body from GitHub:
   ```bash
   gh issue view <number> --repo <owner/repo> --json title,body,labels
   ```

   b. **Parse dependencies** from each issue body: look for the `## Dependencies` section, extract `#<number>` references. For each dependency that is a closed issue, note it as satisfied. For open dependencies within this worktree, determine implementation order.

   c. **Match spec labels to source directories.** From each issue's labels, map `spec:*` labels to source directories:
   - `spec:communication` → `src/ai_company/communication/`
   - `spec:agent-system` → `src/ai_company/engine/`, `src/ai_company/core/`
   - `spec:task-workflow` → `src/ai_company/engine/`
   - `spec:company-structure` → `src/ai_company/core/`, `src/ai_company/config/`
   - `spec:templates` → `src/ai_company/templates/`
   - `spec:providers` → `src/ai_company/providers/`
   - `spec:budget` → `src/ai_company/budget/`
   - `spec:tools` → `src/ai_company/tools/`
   - `spec:hr` → `src/ai_company/core/`
   - `spec:human-interaction` → `src/ai_company/api/`, `src/ai_company/cli/`

   Also read the issue bodies for `§` references to DESIGN_SPEC sections.

   d. **Check which dependency modules exist** on disk (glob the matched directories) to build a concrete file list for the prompt's "Read the relevant source modules" section.

   e. Build the prompt using this template:

   ~~~
   Enter plan mode. You are implementing <phase-description>.

   ## Issues
   - #<N>: <title>
   - #<N>: <title>

   ## Instructions
   1. Read `DESIGN_SPEC.md` sections: <list relevant §sections from issue bodies>
   2. Read the GitHub issues: <gh issue view commands>
   3. Read the relevant source modules: <list directories/files matched from spec labels + dependency parsing>

   ## Scope
   - #<N>: <summarize acceptance criteria from issue body>
   - #<N>: <summarize acceptance criteria from issue body>

   ## Workflow
   - Plan the full implementation before writing any code — present the plan for approval
   - Follow TDD: write tests first, then implement
   - Follow all conventions in CLAUDE.md (immutability, PEP 758, no __future__ imports, structlog logging, etc.)
   - After implementation: create commits on this branch, push with -u, then use /pre-pr-review
   ~~~

   If there are multiple issues in one worktree that have a natural ordering (from dependency parsing or logical sequence), add an `## Implementation order` section.

6. **Present the output** to the user:
   - For each worktree: the `cd` + `claude` command using **Windows-native paths** (e.g. `cd C:\Users\Aurelio\ai-company-wt-delegation-loop-prevention && claude`), followed by the prompt in a code block
   - End with a count: "N worktrees ready. Go."

---

## Command: `cleanup`

Remove worktrees and clean up branches after PRs are merged.

### Steps

1. **List current worktrees:**

   ```bash
   git worktree list
   ```

   If only the main worktree exists, report "No worktrees to clean up." and stop.

2. **Pull latest main:**

   ```bash
   git checkout main && git pull
   ```

3. **Prune remote refs:**

   ```bash
   git fetch --prune
   ```

4. **Check PR merge status** for each non-main worktree's branch:

   ```bash
   gh pr list --repo <owner/repo> --state merged --json headRefName --jq '.[].headRefName'
   gh pr list --repo <owner/repo> --state open --json headRefName,number --jq '.[] | "\(.headRefName) #\(.number)"'
   ```

   For each worktree branch:
   - If PR is **merged**: safe to remove. Proceed.
   - If PR is **open**: warn user — "Branch <name> has open PR #N. Still remove?" Ask via AskUserQuestion.
   - If **no PR found**: warn — "No PR found for <branch>. Still remove?" Ask via AskUserQuestion.

5. **For each approved worktree**, remove it:

   ```bash
   git worktree remove <path>
   ```

   If removal fails (dirty worktree), warn the user and ask via AskUserQuestion whether to force-remove.

6. **Delete local feature branches.** These are squash-merged so git won't recognize them as merged — use `-D`:

   ```bash
   git branch -D <branch1> <branch2> ...
   ```

7. **Verify clean state:**

   ```bash
   git worktree list
   git branch -a
   ```

8. **Show milestone progress** (if determinable). Detect the milestone from the branches/issues that were cleaned up:

   ```bash
   gh issue list --repo <owner/repo> --milestone "<milestone>" --state all --json state --jq '[group_by(.state) | .[] | {state: .[0].state, count: length}]'
   ```

   Report: "Clean. Main up to date, N worktrees removed, N branches deleted. Milestone: X/Y issues closed, Z remaining."

---

## Command: `status`

Show current worktree state and how they compare to main.

### Steps

1. **List worktrees:**

   ```bash
   git worktree list
   ```

2. **For each non-main worktree**, show:
   - Branch name
   - How many commits ahead/behind main:
     ```bash
     git -C <path> rev-list --left-right --count main...<branch>
     ```
   - Whether it has uncommitted changes:
     ```bash
     git -C <path> status --short
     ```

3. **Check for corresponding PRs:**

   ```bash
   gh pr list --repo <owner/repo> --state open --json number,title,headRefName
   ```

   Match each worktree branch to any open PR.

4. **Present a summary table:**

   ```
   Worktree             | Branch                    | vs Main    | PR     | Status
   wt-delegation        | feat/delegation-loop-prev | +5 ahead   | #142   | clean
   wt-parallel          | feat/parallel-execution   | +3 ahead   | —      | 2 modified
   ```

---

## Command: `tree`

Auto-generate a phase/dependency tree view from milestone issues.

### Input format

```
/worktree tree --milestone M4
```

If no milestone specified, try to detect from current worktree branches or ask via AskUserQuestion.

### Steps

1. **Fetch all issues for the milestone:**

   ```bash
   gh issue list --repo <owner/repo> --milestone "<milestone-title>" --state all --limit 100 --json number,title,state,labels,body
   ```

   Find the milestone title by querying:
   ```bash
   gh api repos/<owner/repo>/milestones --jq '.[] | select(.title | test("<milestone-pattern>")) | {number, title}'
   ```

2. **Parse dependency graph.** For each issue, extract `## Dependencies` section and resolve `#<N>` references. Build an adjacency list.

3. **Compute tiers** using topological sort:
   - Tier 0: issues with no open M-internal dependencies (all deps are closed or external)
   - Tier 1: depends only on Tier 0 issues
   - Tier N: depends on Tier N-1 issues
   - Flag circular dependencies as errors

4. **Identify current active worktrees** (if any):
   ```bash
   git worktree list
   ```

5. **Render the tree** showing:
   - Each tier with issues, their state (DONE/OPEN), priority labels
   - Which directories each issue touches (from spec labels)
   - Current worktree assignments (if active)
   - Phase groupings (suggest phases based on tiers + directory conflict analysis)

   Format:
   ```
   MILESTONE: M4 — Communication & Multi-Agent Orchestration (15/19 done)

   TIER 0 — No dependencies (all prereqs closed)
     ✅ #8   Message bus                    [critical]  communication/
     ✅ #10  Agent-to-agent messaging       [critical]  communication/
     ⬜ #134 Plan-and-Execute loop          [medium]    engine/

   TIER 1 — Depends on Tier 0
     ✅ #12  Hierarchical delegation        [high]      communication/, engine/
     ...
   ```

6. **Show summary:**
   ```
   Done: N/M issues
   Open: X issues across Y tiers
   Suggested next phase: Z parallel worktrees
   ```

---

## Command: `rebase`

Update all worktrees to latest main. Pulls main first, then rebases clean worktrees.

### Steps

1. **Pull main first:**

   ```bash
   git checkout main && git pull
   ```

2. **For each non-main worktree**, check for local commits beyond main:

   ```bash
   git -C <path> rev-list --count main..<branch>
   ```

   - If **0 commits ahead**: safe to rebase.
   - If **has commits**: warn the user — "Worktree <name> has N local commits. Rebase may cause conflicts." Ask via AskUserQuestion: rebase anyway / skip / abort all.

3. **Check for uncommitted changes:**

   ```bash
   git -C <path> status --short
   ```

   If dirty, warn and skip (don't rebase dirty worktrees).

4. **For approved worktrees**, rebase:

   ```bash
   git -C <path> rebase main
   ```

   If rebase fails (conflicts), abort and report:
   ```bash
   git -C <path> rebase --abort
   ```

5. **Verify:**

   ```bash
   git -C <path> log --oneline -1
   ```

6. Report: "N worktrees rebased to <commit>. M skipped (have local commits or dirty state)."

---

## Rules

- **Never force-remove** a worktree without asking the user first.
- **Never delete branches** without checking PR merge status first.
- **Always check `.claude/` local files exist** before copying — warn if missing.
- **Repo name detection**: extract from the current directory basename (e.g. `ai-company`).
- **Owner/repo detection**: extract from `git remote get-url origin`.
- **Windows paths**: all `cd` commands in prompts use backslash Windows-native paths (e.g. `C:\Users\...`).
- Worktree directories are always siblings of the main repo directory (`../`).
- When generating prompts, read the actual issue bodies — do not guess or use stale information.
- Parse `spec:*` labels to auto-match source directories for prompt generation.
- Parse `## Dependencies` sections to auto-detect implementation order.
- If `$ARGUMENTS` is empty or doesn't match a command, show a brief usage guide:
  ```
  /worktree setup <definitions>   — Create worktrees with prompts
  /worktree setup --milestone M4 --issues #26,#30  — Milestone-aware setup
  /worktree cleanup                — Remove worktrees after merge
  /worktree status                 — Show worktree state
  /worktree tree --milestone M4    — Dependency tree view
  /worktree rebase                 — Update worktrees to latest main
  ```
