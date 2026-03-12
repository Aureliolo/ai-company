---
name: no-future-annotations
enabled: true
event: file
pattern: from\s+__future__\s+import\s+annotations
action: block
---

**`from __future__ import annotations` is forbidden in this project.**

Python 3.14 has PEP 649 native lazy annotations, making this import unnecessary.
The project CLAUDE.md explicitly states: "No `from __future__ import annotations`".

Remove this import and use native type hints directly.
