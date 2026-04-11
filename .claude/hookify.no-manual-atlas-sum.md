---
name: no-manual-atlas-sum
enabled: true
event: edit
pattern: atlas\.sum
action: block
---

# Do not manually edit atlas.sum

Atlas manages `atlas.sum` checksums automatically. Manual edits break the header hash and create checksum mismatches that cascade into migration failures.

**Correct workflow for consolidating PR-local migrations:**

1. Restore `atlas.sum` from the PR base branch: use Write tool with content from `git show <base_branch>:<path>/atlas.sum`
2. Delete the PR's migration files: `rm <path>/<migration>.sql`
3. Run `atlas migrate diff --env <env> <name>` to regenerate one consolidated migration

This restores a valid checksum baseline, then lets Atlas generate the new migration and update atlas.sum in one atomic operation. Never manually add, remove, or modify lines in atlas.sum.
