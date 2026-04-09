---
name: no-atlas-rehash
enabled: true
event: bash
pattern: atlas\s+migrate\s+hash
action: block
---

**BLOCKED: Do not rehash Atlas migrations.**

`atlas migrate hash` rewrites `atlas.sum` checksums. Post-release, this would silently invalidate existing database installations.

If you see a checksum mismatch after rebase:
1. The baseline was likely regenerated -- check `git diff` on the baseline `.sql`
2. If schema actually changed, create a **new migration**: `atlas migrate diff --env sqlite <name>`
3. Never modify or rehash an existing migration that has been released

Pre-alpha exception: if genuinely needed during development, ask the user first.
