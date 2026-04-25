## [0.7.1](https://github.com/Aureliolo/synthorg/compare/v0.7.0...v0.7.1) (2026-04-20)


### Features

* **budget:** persist currency on every cost row + Postgres/SQLite parity slice ([#1454](https://github.com/Aureliolo/synthorg/issues/1454)) ([3f2b9f7](https://github.com/Aureliolo/synthorg/commit/3f2b9f7e0b55b6df5281d64c79f6fec1f7b26424))
* **telemetry:** deployment environment tagging + Docker /info enrichment + silence Logfire introspection ([#1459](https://github.com/Aureliolo/synthorg/issues/1459)) ([7981bf6](https://github.com/Aureliolo/synthorg/commit/7981bf66b3c714e0903870221fd14945cbeeea4c))
* wire project telemetry, live NATS health probe, web healthcheck ([#1453](https://github.com/Aureliolo/synthorg/issues/1453)) ([eeb9492](https://github.com/Aureliolo/synthorg/commit/eeb9492e5e23d4bfe3d371ae3b3bd0cef3cf87d9))
* **wizard:** fix setup-wizard UX issues and stale-cookie recovery ([#1463](https://github.com/Aureliolo/synthorg/issues/1463)) ([6ff9874](https://github.com/Aureliolo/synthorg/commit/6ff98746cbadd3776db9962efa83f4b7ad20afc7))


### Bug Fixes

* **docker:** drop ':latest' default on backend BASE_IMAGE ARG ([#1465](https://github.com/Aureliolo/synthorg/issues/1465)) ([254f043](https://github.com/Aureliolo/synthorg/commit/254f043f68a5e255c1bfac07269cfc00bfa66ba2)), closes [#1464](https://github.com/Aureliolo/synthorg/issues/1464)
* split remaining TypeScript files + full verification ([#1481](https://github.com/Aureliolo/synthorg/issues/1481)) ([4338a74](https://github.com/Aureliolo/synthorg/commit/4338a748be6a35b31e6e64837012111005d75a2f))


### Refactoring

* split oversize Python files + Go functions to comply with size limits ([#1473](https://github.com/Aureliolo/synthorg/issues/1473)) ([5c17c76](https://github.com/Aureliolo/synthorg/commit/5c17c762ea3cbdf372dc442b8568fbeb8e6e69a8))


### Maintenance

* consolidate Renovate lock-file PRs and delete orphan root package-lock.json ([#1482](https://github.com/Aureliolo/synthorg/issues/1482)) ([5b22810](https://github.com/Aureliolo/synthorg/commit/5b22810b23f22801701626284930af31dcd5838b))
* Lock file maintenance ([#1478](https://github.com/Aureliolo/synthorg/issues/1478)) ([7e69dce](https://github.com/Aureliolo/synthorg/commit/7e69dceb7bfca0a60ad7c5ae6b6ca0bdde656a11))
---

## CLI Installation

**Linux / macOS:**

```bash
curl -sSfL https://synthorg.io/get/install.sh | bash
```

> **Pin to this release:** set `SYNTHORG_VERSION=v0.7.1` before running.

## Container Images

All images are signed with cosign.

---

## Verification

### CLI Checksums (SHA-256)

| Archive | SHA-256 |
|---------|---------|
| `synthorg_linux_amd64.tar.gz` | `78160c46f4f1ba1069bbc6997849d666682cfc39cdf0f29924e86a20b7d1689c` |
