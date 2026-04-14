# CLI (Go Binary)

Go tooling requires the module root as cwd. Use `go -C cli` which changes directory internally without affecting the shell. Never use `cd cli` -- it poisons the cwd for all subsequent Bash calls. golangci-lint is registered as a `tool` in `cli/go.mod` so it runs via `go -C cli tool golangci-lint`.

## Quick Commands

```bash
go -C cli build -o synthorg ./main.go                                  # build CLI
go -C cli test ./...                                                   # run tests (fuzz targets run seed corpus only without -fuzz flag)
go -C cli vet ./...                                                    # vet
go -C cli tool golangci-lint run                                       # lint
go -C cli test -fuzz=FuzzYamlStr -fuzztime=30s ./internal/compose/     # fuzz example
```

## Package Structure

```text
cli/
  cmd/            # Cobra commands (init, start, stop, status, logs, doctor, update, cleanup, wipe, config, etc.), global options, exit codes, env var constants
  internal/       # version, config, docker, compose, health, diagnostics, images, selfupdate, completion, ui, verify
```

## Global Flags

All commands accept these persistent flags (precedence: flag > env var > config > default):

| Flag | Short | Env Var | Description |
|------|-------|---------|-------------|
| `--data-dir` | | `SYNTHORG_DATA_DIR` | Data directory (default: platform-appropriate) |
| `--skip-verify` | | `SYNTHORG_NO_VERIFY` / `SYNTHORG_SKIP_VERIFY` | Skip image signature verification |
| `--quiet` | `-q` | `SYNTHORG_QUIET` | Errors only, no spinners/hints/boxes |
| `--verbose` | `-v` | | Increase verbosity (`-v`=verbose, `-vv`=trace) |
| `--no-color` | | `NO_COLOR`, `CLICOLOR=0`, `TERM=dumb` | Disable ANSI color output |
| `--plain` | | | ASCII-only output (no Unicode, no spinners) |
| `--json` | | | Machine-readable JSON output |
| `--yes` | `-y` | `SYNTHORG_YES` | Auto-accept all prompts (non-interactive) |
| `--help-all` | | | Show help for all commands (recursive) |

Config-driven overrides (set via `synthorg config set`): `color never` implies `--no-color`, `color always` forces color on non-TTYs, `output json` implies `--json`, `hints` mode is config-only (always/auto/never).

## Hint Tiers

The CLI uses four hint tiers with different visibility rules per `hints` mode. When adding hints, choose the tier that matches the intent:

| Tier | `always` | `auto` | `never` | `--quiet` | Use for |
|------|----------|--------|---------|-----------|---------|
| `HintError` | shown | shown | shown | suppressed | Error recovery (always visible unless quiet) |
| `HintNextStep` | shown | shown | shown | suppressed | Natural next action, destructive-action feedback |
| `HintTip` | shown | once/session | suppressed | suppressed | Config automation suggestions (e.g. `auto_pull`) |
| `HintGuidance` | shown | suppressed | suppressed | suppressed | Flag/feature discovery (e.g. `--watch`, `--keep N`) |

`HintTip` deduplicates within a session (same message shown at most once). `HintGuidance` is invisible in the default `auto` mode -- only users who opt in with `synthorg config set hints always` see it.

## Additional Env Vars

No corresponding flag -- settable via env var or `config set`:

| Env Var | Description |
|---------|-------------|
| `SYNTHORG_LOG_LEVEL` | Override backend log level |
| `SYNTHORG_BACKEND_PORT` | Override backend API port |
| `SYNTHORG_WEB_PORT` | Override web dashboard port |
| `SYNTHORG_CHANNEL` | Override release channel (stable/dev) |
| `SYNTHORG_IMAGE_TAG` | Override container image tag |
| `SYNTHORG_AUTO_UPDATE_CLI` | Auto-accept CLI self-updates |
| `SYNTHORG_AUTO_PULL` | Auto-accept container image pulls |
| `SYNTHORG_AUTO_RESTART` | Auto-restart containers after update |
| `SYNTHORG_TELEMETRY` | Enable anonymous product telemetry (true/false) |
| `SYNTHORG_FINE_TUNE_IMAGE` | Override fine-tune container image digest (set by CLI verification) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Runtime error |
| 2 | Usage error (bad arguments) |
| 3 | Unhealthy (backend/containers) |
| 4 | Unreachable (Docker not available) |
| 10 | Updates available (`--check`) |

## Config Subcommands

`synthorg config <subcommand>`:

| Subcommand | Description |
|------------|-------------|
| `show` | Display all current settings (default when no subcommand) |
| `get <key>` | Get a single config value (20 gettable keys) |
| `set <key> <value>` | Set a config value (19 settable keys, compose-affecting keys trigger regeneration) |
| `unset <key>` | Reset a key to its default value |
| `list` | Show all keys with resolved value and source (env/config/default) |
| `path` | Print the config file path |
| `edit` | Open config file in $VISUAL/$EDITOR |

Settable keys: `auto_apply_compose`, `auto_cleanup`, `auto_pull`, `auto_restart`, `auto_start_after_wipe`, `auto_update_cli`, `backend_port`, `channel`, `color`, `docker_sock`, `fine_tuning`, `hints`, `image_tag`, `log_level`, `output`, `sandbox`, `telemetry_opt_in`, `timestamps`, `web_port`. Keys that affect Docker compose (`backend_port`, `web_port`, `sandbox`, `docker_sock`, `fine_tuning`, `image_tag`, `log_level`, `telemetry_opt_in`) trigger automatic `compose.yml` regeneration.

## Per-Command Flags

| Command | Flags |
|---------|-------|
| `init` | `--backend-port`, `--web-port`, `--sandbox`, `--log-level` (required for non-interactive mode); optional: `--image-tag`, `--channel`, `--bus-backend`, `--persistence-backend`, `--postgres-port` |
| `start` | `--no-wait`, `--timeout`, `--no-pull`, `--dry-run`, `--no-detach`, `--no-verify` |
| `stop` | `--timeout`/`-t`, `--volumes` |
| `status` | `--watch`/`-w`, `--interval`, `--wide`, `--no-trunc`, `--services`, `--check` |
| `logs` | `--follow`/`-f`, `--tail`, `--since`, `--until`, `--timestamps`/`-t`, `--no-log-prefix` |
| `update` | `--dry-run`, `--no-restart`, `--timeout`, `--cli-only`, `--images-only`, `--check` |
| `cleanup` | `--dry-run`, `--all`, `--keep N` |
| `backup create` | `--output`/`-o`, `--timeout` |
| `backup list` | `--limit`/`-n`, `--sort` |
| `backup restore` | `--confirm`, `--dry-run`, `--no-restart`, `--timeout` |
| `wipe` | `--dry-run`, `--no-backup`, `--keep-images` |
| `doctor` | `--checks`, `--fix` |
| `version` | `--short` |
| `uninstall` | `--keep-data`, `--keep-images` |

## Persistence Backends

The CLI orchestrates two persistence backends:

| Backend | Flag | Port | Data volume | When to use |
|---------|------|------|-------------|-------------|
| `sqlite` (default) | `--persistence-backend sqlite` | n/a (in-process) | `synthorg-data` | Single-node, development, small deployments |
| `postgres` | `--persistence-backend postgres` | `3002` (default, override with `--postgres-port`) | `synthorg-pgdata` | Multi-instance, production, high concurrency |

### Postgres orchestration

When `--persistence-backend postgres` is selected, `synthorg init`:

1. Adds a `postgres:18-alpine` service to the generated `compose.yml` (non-root user `70:70`, read-only rootfs, dropped capabilities, pg_isready healthcheck, named volume `synthorg-pgdata`).
2. Generates a 32-byte URL-safe random password via `crypto/rand` and persists it to `config.json` (`postgres_password`). Re-init preserves the existing password to avoid breaking the running container.
3. Wires `SYNTHORG_DATABASE_URL=postgresql://synthorg:<password>@postgres:5432/synthorg` into the backend container's environment. The SQLite-only `SYNTHORG_DB_PATH` variable is omitted.
4. Declares `depends_on: postgres: condition: service_healthy` on the backend service so backend startup blocks until Postgres accepts connections.

`synthorg start` brings up Postgres first (via compose ordering), then the backend applies Atlas migrations on connection. `synthorg stop` preserves `synthorg-pgdata` unless `--volumes` is passed. `synthorg status --wide` reports Postgres container health plus the `synthorg-pgdata` volume size.

Port layout: `3000` web / `3001` backend / `3002` postgres / `3003` NATS client. `generate.go` validates port collisions: web vs backend always; postgres vs web/backend/NATS when postgres enabled; NATS vs web/backend when distributed bus mode is active.
