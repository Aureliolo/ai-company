Dev build #5 toward v0.7.3

**Commit:** 5a4e672
**Full pipeline:** Docker images, CLI binaries, cosign signatures, and SLSA provenance will be attached by downstream workflows.

> This is a pre-release for testing. Use `synthorg config set channel dev` to opt in.
---

## CLI Installation

**Linux / macOS:**

```bash
curl -sSfL https://synthorg.io/get/install.sh | bash
```

## Container Images

| Image | Command |
|-------|---------|
| Backend | `docker pull ghcr.io/aureliolo/synthorg-backend:0.7.3-dev.5` |
