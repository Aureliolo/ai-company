---
name: no-manual-atlas-sum
enabled: true
event: edit
pattern: atlas\.sum
action: block
---

# Do not manually edit atlas.sum

Atlas manages `atlas.sum` checksums automatically. Manual edits via Write/Edit break the header hash and cascade into migration failures.

**Correct workflow for consolidating PR-local migrations:**

1. Restore `atlas.sum` from the PR base branch via git (NOT via Write tool):
   `git restore --source=origin/<base_branch> -- <path>/atlas.sum`
2. Delete the PR's migration files: `rm <path>/<migration>.sql`
3. Run `atlas migrate diff --env <env> <name>` to regenerate one consolidated migration

`git restore` writes a byte-exact copy from the base branch's git blob, preserving the valid checksum baseline. Atlas then updates `atlas.sum` atomically when it generates the new migration. Never use Write/Edit tools on `atlas.sum`.
