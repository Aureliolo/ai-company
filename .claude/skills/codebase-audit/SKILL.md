---
description: "Deep codebase audit: launches specialized parallel agents to find issues, validates findings, groups into work packages, and creates GitHub issues"
argument-hint: "<scope: full | src/ | src/synthorg/ | web/ | cli/ | docs/ | site/ | .github/ | ci | docker/> [--report-only] [--quick]"
allowed-tools: ["Agent", "Bash", "Read", "Glob", "Grep", "WebFetch", "WebSearch", "AskUserQuestion", "mcp__github__issue_write", "mcp__github__issue_read", "mcp__github__list_issues", "mcp__github__search_issues"]
---

# /codebase-audit -- Deep Codebase Audit

Launch a swarm of specialized agents to find issues across the entire codebase (or a targeted scope), validate all findings against actual code, group into developer-friendly work packages, and optionally create GitHub issues.

## Key Principles (from battle-tested sessions)

1. **Never present unvalidated findings** -- validation is mandatory before presenting findings to the user
2. **Research architecture BEFORE auditing** -- agents that don't understand the system produce false positives
3. **Skepticism is required** -- "100% clean" results are suspicious and trigger deeper investigation
4. **Group by code proximity, NOT severity** -- work packages are what a developer would naturally fix together
5. **No meta/tracking issues** -- every finding is a real issue or part of a real work package
6. **Existing issue dedup happens TWICE** -- once in agent prompts, once after validation
7. **Fix everything valid** -- no deferring, no "out of scope", no "future work"

---

## Phase 0: Parse Arguments & Determine Scope

Parse the user's argument to determine audit scope:

| Argument | Scope | Agent Categories |
|----------|-------|------------------|
| `full` (default) | Entire codebase | All categories |
| `src/` or `src/synthorg/` | Python backend only | Python-focused categories |
| `web/` | React dashboard only | Frontend categories |
| `cli/` | Go CLI only | Go categories |
| `docs/` or `site/` | Documentation/site | Docs/content categories |
| `.github/` or `ci` | CI/CD only | CI/workflow categories |
| `docker/` | Docker/compose only | Infrastructure categories |
| `--report-only` | Any scope | Skip issue creation, report only |
| `--quick` | Any scope | Skip Phase 5 deep dive on zero-finding categories |

If no argument given, default to `full`.

---

## Phase 1: Gather Context

**This phase is CRITICAL. Agents without context produce false positives.**

### Step 1a: Fetch existing GitHub issues

```bash
gh issue list --repo OWNER/REPO --state open --limit 200 --json number,title,labels
```

Parse into a compact reference list: `#N: title [labels]`. This list is passed to EVERY audit agent.

### Step 1b: Research project architecture

Read key architectural files to build context that agents need. At minimum:

1. **CLAUDE.md** (already in context) -- project conventions, code standards, testing rules
2. **Observability stack** -- read `src/synthorg/observability/__init__.py`, `_logger.py`, `sinks.py`, `setup.py`, `correlation.py` to understand logging architecture, sink routing, correlation ID system
3. **DI/wiring** -- read `src/synthorg/api/auto_wire.py` and `src/synthorg/api/lifecycle.py` to understand service initialization
4. **Testing setup** -- read `conftest.py` files, `pyproject.toml` test config section
5. **Design spec pointer** -- read `docs/DESIGN_SPEC.md` to know which spec pages exist

Produce a **Architecture Brief** (200-400 words) summarizing:
- Logging: how it works, sink routing rules, correlation IDs
- DI: how services are wired, lifecycle phases
- Testing: markers, parallelism, async mode, coverage requirements
- Key conventions: immutability, error handling, vendor-agnostic naming

This brief is injected into every agent's prompt.

### Step 1c: Identify scope-specific files

If scope is targeted (not `full`), glob the target directory to understand what's there.

---

## Phase 2: Select & Launch Audit Agents

### Agent Roster

Select agents based on scope. Each agent searches for ONE type of issue only.

#### Python Backend Agents (scope includes `src/`)

| Agent | What It Searches For |
|-------|---------------------|
| `missing-logging` | Business logic modules without `get_logger`, error paths that don't log before raising, state transitions without INFO logging, missing DEBUG at decision points |
| `event-constants` | Log calls using raw strings instead of event constants from `observability/events/` |
| `silent-errors` | Bare `except:`, `except Exception: pass`, catch blocks that swallow without logging |
| `test-coverage` | Public modules with no corresponding test file, empty test files |
| `flaky-tests` | Unmocked time, real asyncio.sleep in tests, timing-dependent assertions, skipped tests |
| `wiring-lifecycle` | Incorrectly wired services, missing DI, lifecycle gaps, protocol implementations incomplete |
| `dead-code` | Unreachable functions, unused imports, orphaned modules |
| `todo-fixme` | Unresolved TODOs that should be tracked as issues |
| `spec-drift` | Implementation diverging from design spec behavior |
| `api-consistency` | REST endpoint issues: wrong status codes, missing validation, inconsistent patterns |
| `async-patterns` | Bare create_task, missing await, blocking in async, race conditions |
| `immutability` | Mutable defaults, in-place mutation of frozen models, missing deepcopy |
| `missing-validation` | System boundary inputs without validation (API params, config loading, external data) |
| `type-hints` | Missing return types, bare Any, missing NotBlankStr on identifiers |
| `vendor-names` | Real vendor names used where generic names should be (per CLAUDE.md rules) |
| `observability-gaps` | Sink routing gaps, correlation ID propagation drops, missing event constant modules |

#### Frontend Agents (scope includes `web/`)

| Agent | What It Searches For |
|-------|---------------------|
| `react-dashboard` | Broken API refs, missing error handling, console.log in prod, TypeScript gaps, a11y |

#### Go CLI Agents (scope includes `cli/`)

| Agent | What It Searches For |
|-------|---------------------|
| `go-cli` | Ignored errors, resource leaks, missing error wrapping, cross-platform issues |

#### Infrastructure Agents

| Agent | What It Searches For |
|-------|---------------------|
| `docker-infra` | Dockerfile issues, compose config, port security, healthchecks (run when scope includes `docker/`) |
| `ci-workflows` | Missing timeouts, script injection, permissions gaps, silent failures (run when scope includes `.github/` or `ci`) |

#### Documentation Agents (scope includes `docs/` or `site/`)

| Agent | What It Searches For |
|-------|---------------------|
| `docs-consistency` | Broken links, outdated info, wrong commands, inconsistent terminology |
| `landing-site` | SEO gaps, broken links, a11y issues, missing error pages |

#### Cross-Cutting Agents (always included)

| Agent | What It Searches For |
|-------|---------------------|
| `security-gaps` | Cross-stack security issues: SSRF, XSS, injection vectors, hardcoded secrets across all languages |
| `dependency-issues` | Unused deps, missing deps, version conflicts across all package managers |
| `docstring-gaps` | Public classes/functions missing Google-style docstrings |

### Agent Prompt Template

Every agent receives this structure:

```text
## Task
You are searching the codebase for ONE specific type of issue: {ISSUE_TYPE}.

## Architecture Context
{ARCHITECTURE_BRIEF from Phase 1b}

## Existing Open Issues (do NOT report these)
{ISSUE_LIST from Phase 1a}

## Scope
Search: {SCOPE_DIRECTORIES}

## Rules
1. For each finding, report: file path, line number, what's wrong, operational impact
2. Cross-reference against the existing issues list -- only report what's NOT already tracked
3. BE SKEPTICAL of your own findings -- verify each one by reading the actual code
4. If you find ZERO issues, state that clearly but also explain what you checked
5. Do NOT flag things that are intentional design decisions (check comments, docstrings)
6. Rate each finding: CONFIRMED (verified in code) or LIKELY (needs validation)

## What to Search For
{CATEGORY-SPECIFIC INSTRUCTIONS}
```

### Launch

Launch ALL selected agents in parallel using the Agent tool with `run_in_background: true`. Give each a descriptive `name` for tracking.

Track agent count and report to user: "Launched N audit agents in parallel. Waiting for results..."

---

## Phase 3: Collect & Deduplicate

As agents complete, collect their findings. Once ALL agents have reported:

### Step 3a: Check for suspicious clean results

If any agent reported zero findings, flag it:
- "Agent `{name}` found zero issues. This may be accurate or the agent may have been too shallow."
- These categories are candidates for Phase 5 (deep dive).

### Step 3b: Merge all findings into a single list

Combine findings from all agents into one flat list with columns:
- Source agent
- File path : line number
- Category
- Description
- Agent's self-assessed confidence (CONFIRMED / LIKELY)

### Step 3c: Deduplicate

- Multiple agents may flag the same line/issue (e.g., security + validation both flag missing input checks)
- Merge duplicates, keep the most detailed description
- Remove findings that match existing open GitHub issues (by file path + description similarity)

---

## Phase 4: Validate Findings

**MANDATORY. Never skip this phase.**

Launch validation agents in parallel. Each validation agent gets a batch of 8-12 findings and is instructed to:

1. Read the actual source file at the reported line number
2. Verify the issue exists as described
3. Check if the "issue" is actually intentional (read comments, docstrings, related code)
4. Check if CI/build/tests handle it in a way the audit agent missed
5. Classify each finding:
   - **CONFIRMED** -- verified in code, real issue
   - **LIKELY CONFIRMED** -- code suggests the issue but edge case unclear
   - **LIKELY FALSE** -- probably not a real issue (explain why)
   - **FALSE POSITIVE** -- definitely not an issue (explain why)
6. For intentional patterns (e.g., graceful shutdown error swallowing), mark as "CONFIRMED but INTENTIONAL" -- these are excluded from work packages

### Validation Agent Prompt Template

```text
Validate these audit findings by reading the ACTUAL SOURCE CODE.
For each finding, determine: CONFIRMED, LIKELY CONFIRMED, LIKELY FALSE, or FALSE POSITIVE.

For each:
1. Read the file at the reported line number
2. Quote the actual code
3. Check if it's intentional (read surrounding comments, docstrings)
4. Check if CI, tests, or build pipelines handle it
5. Give a clear verdict with evidence

{BATCH OF FINDINGS}
```

### After validation

- Remove all FALSE POSITIVE and LIKELY FALSE findings
- Keep CONFIRMED and LIKELY CONFIRMED
- Mark CONFIRMED-but-INTENTIONAL as excluded (note in report but don't create issues)
- Calculate false positive rate: `removed / total`
- Report: "Validated N findings. Removed M false positives (X%). N remaining confirmed findings."

---

## Phase 5: Deep Dive on Suspicious Clean Results

For each audit category that found ZERO issues in Phase 2:

1. **Research the relevant architecture first** -- read the actual implementation files to understand how the system works
2. **Craft a targeted, informed prompt** -- include specific architectural details (e.g., "the observability stack uses structlog with 11 sinks routed by logger name prefix via _SINK_ROUTING in sinks.py")
3. **Launch a second agent** with the enriched prompt and explicit instructions: "The first audit found nothing. Dig deeper. Check specific functions, look for subtle gaps, verify edge cases."
4. **Validate any new findings** (same as Phase 4)
5. Add validated findings to the main list

Skip this phase if the user passed `--quick` or if the zero-finding categories are genuinely well-covered (e.g., dependencies audit finding nothing is believable).

---

## Phase 6: Present Validated Findings

Present the validated, deduplicated findings to the user. Format:

### Summary Table

```text
| # | Finding | File:Line | Category | Verdict |
|---|---------|-----------|----------|---------|
| 1 | Description | path:123 | category | CONFIRMED |
| ... | ... | ... | ... | ... |
```

### Statistics

- Total findings: N
- False positives removed: M (X%)
- Confirmed: N1, Likely confirmed: N2
- Intentional (excluded): N3
- Categories with zero findings: list

### User Gate

If `--report-only` was passed, skip this gate and go directly to the markdown report (option 3 below).

Otherwise, ask the user:
1. **"Proceed to group into work packages and create issues" (Recommended)**
2. "Show me the full detail for each finding first"
3. "Export as markdown report only (no issues)"

---

## Phase 7: Group into Work Packages

**Group by code proximity, NOT by severity.**

### Grouping Rules

1. **Same directory/module** -- findings touching the same `src/synthorg/<module>/` go together
2. **Same file** -- multiple findings in one file always go in the same package
3. **Dependency chain** -- if fixing A requires fixing B first, bundle them
4. **Same developer context** -- what would a developer naturally fix in one sitting?
5. **Target medium scope** -- each package should be a meaningful PR, not too small (1 finding) or too large (15+ findings)
6. **Never group by severity** -- a HIGH and LOW in the same file go together; a HIGH and HIGH in different modules do NOT

### Common Groupings

These patterns recur across audits:
- **API controller sweep** -- validation, response patterns, auth hardening (all in `api/controllers/`)
- **Observability fixes** -- sink routing, correlation, event constants (all in `observability/`)
- **Test quality** -- flaky fixes + missing coverage (all in `tests/`)
- **CI hardening** -- timeouts, permissions, script safety (all in `.github/`)
- **Documentation** -- content fixes across `docs/` and `site/`
- **Language-specific** -- Go fixes together, React fixes together

### Standalone features

If a finding is a "feature not yet implemented" (spec drift with TODO/stub), it can be its own issue if medium+ scope. Do NOT create meta/tracking issues -- each issue must be implementable on its own.

### Present to User

Show the proposed work packages:

```text
## Proposed Work Packages (N total)

### WP1: Name
| # | Finding |
|---|---------|
| 1 | ... |
| 2 | ... |
```

**Rationale:** Why these go together.

```text
### WP2: Name
...
```

Ask: "Create issues for all N work packages? Or adjust groupings first?"

---

## Phase 8: Final Issue Dedup & Creation

### Step 8a: Final dedup against existing issues

Before creating, do one final check:

```bash
gh issue list --repo OWNER/REPO --state open --limit 200 --json number,title,labels
```

For each work package, search for title/description overlap with existing issues. If a finding is already covered by an existing issue, either:
- Remove it from the work package
- Note "extends #NNN" in the new issue body

### Step 8b: Create issues

For each work package, create a GitHub issue with:

- **Title**: `<type>: <concise description>` (matching commit convention: fix, feat, chore, docs, test)
- **Body**:
  - `## Summary` -- 1-2 sentences
  - `## Findings` -- table of findings with file:line, description
  - `## Files to Modify` -- list of files that need changes
  - Design spec references if applicable
- **Labels**: appropriate type/scope/spec labels

Use the `mcp__github__issue_write` tool or `gh issue create` via Bash.

**IMPORTANT**: Never use em-dashes or non-ASCII punctuation in issue bodies (project convention).

### Step 8c: Report

Present the complete list of created issues:

```text
| WP | Issue | Title |
|----|-------|-------|
| 1 | #NNN | ... |
| ... | ... | ... |
```

---

## Rules

1. **NEVER present unvalidated findings to the user.** Validation (Phase 4) is mandatory.
2. **ALWAYS research architecture before auditing.** Phase 1b is not optional.
3. **Be skeptical of clean results.** Zero findings triggers Phase 5 deep dive.
4. **Group by code proximity, NEVER by severity.** What files does a developer touch together?
5. **No meta/tracking issues.** Every issue must be directly implementable.
6. **Dedup twice.** Once in agent prompts (Phase 2), once before issue creation (Phase 8a).
7. **All agents run in parallel.** Never launch agents sequentially when they're independent.
8. **Agent prompts include architecture context.** Never launch a "blind" agent.
9. **Intentional patterns are not bugs.** Graceful shutdown error swallowing, defensive cleanup, etc. are valid patterns -- exclude from issues but note in report.
10. **Respect project conventions.** Read CLAUDE.md, use correct commands (`uv run python -m pytest`, not `uv run pytest`), no vendor names, etc.
11. **Default to creating issues.** Unless user passes `--report-only`, the skill creates issues.
12. **Never push code.** This skill audits and creates issues -- it does not fix code.
