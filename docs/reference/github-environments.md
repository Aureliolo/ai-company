# GitHub Deployment Environments

SynthOrg uses GitHub deployment environments to gate workflow jobs that carry
elevated permissions or access sensitive secrets. Each environment has a
branch allowlist (deployment branch policy) so the job only runs when the
workflow was triggered from an expected ref.

Policies cannot be declared in workflow YAML -- they live on the GitHub
environment itself. Apply them via `scripts/configure_environments.sh`.

## Current environments

| Environment | Branch policy | Triggered by |
|---|---|---|
| `github-pages` | `main` | `pages.yml` push to main |
| `release` | `main` | `release.yml` + `dev-release.yml` + `auto-rollover.yml` + `graduate.yml` + `test-signing.yml` (main-scoped), `finalize-release.yml:publish` (workflow_run resolves `github.ref` to main). Holds `RELEASE_BOT_APP_ID` + `RELEASE_BOT_APP_PRIVATE_KEY`. |
| `release-tags` | `v*` | `cli.yml:cli-release` + `docker.yml:update-release` (v* tag pushes). Structural ref gate only; no privileged secrets. |
| `image-push` | `main`, `v*` | `docker.yml` `*-publish` jobs (4 apko base pushes + 5 app image pushes) on main and v* refs |
| `apko-lock` | `main` | `apko-lock.yml` schedule + workflow_dispatch |
| `cloudflare-preview` | _none_ (see below) | `pages-preview.yml` pull_request events |
| `atlas` | _none_ (see below) | `ci.yml:schema-validate` push + pull_request |

The release path is intentionally split into two environments. GitHub's
deployment branch policies only match ref *names* -- they do NOT verify
that a tag's commit is reachable from an allowed branch. Admitting `v*`
on the secret-bearing environment would let any `v`-prefixed tag
(including one forged on an unmerged feature branch) unlock the App
credentials. Keeping `release` main-only and routing tag-only jobs
through `release-tags` preserves the structural ref gate without
exposing the App.

## Why `cloudflare-preview` and `atlas` have no branch policy

GitHub's deployment branch policies match against `github.ref` using fnmatch,
but only for refs under `refs/heads/*` (branches) and `refs/tags/*` (tags).
For `pull_request` event workflows, `github.ref` is `refs/pull/<N>/merge`,
which cannot be matched by any branch-type policy.

`cloudflare-preview` only runs on `pull_request` events, so a branch policy
would either:

- block every PR preview (if set to `main`), or
- admit everything (if set to `*`), providing no real protection.

`atlas` runs on both `push` and `pull_request`, so a `main`-only policy would
block the migration validation gate on every PR.

In both cases the workflow-level gate is the actual control:

- `pages-preview.yml:deploy-preview` / `cleanup-preview`: gated on
  `same_repo == 'true'` so fork PRs cannot access Cloudflare secrets.
- `ci.yml:schema-validate`: runs only through trusted SynthOrg CI paths;
  the environment protects the `ATLAS_TOKEN` secret but does not restrict
  which refs can reach it.

If GitHub ever extends deployment branch policies to cover PR refs, revisit
these two entries in `scripts/configure_environments.sh`.

## Applying policies

Run once after merging SUP-1, and whenever a new environment is added:

```bash
# Preview the API calls (safe, default)
bash scripts/configure_environments.sh

# Apply
bash scripts/configure_environments.sh --apply
```

The script is a reconciler: on `--apply` the final state of each environment's
branch policies exactly matches the `ENV_CONFIG` table inside the script.
Missing policies are `POST`-ed (with `HTTP 422` already-exists treated as a
no-op), and any extra policy not in the desired set is `DELETE`-d. Requires a
`gh` CLI authenticated with the `repo` scope (classic PAT/OAuth) or
`administration:write` (fine-grained PATs/GitHub Apps) -- see the
[deployments API docs](https://docs.github.com/rest/deployments/environments).

## Verifying policies

```bash
gh api repos/Aureliolo/synthorg/environments/apko-lock \
  --jq '.deployment_branch_policy, .name'
gh api repos/Aureliolo/synthorg/environments/apko-lock/deployment-branch-policies \
  --jq '.branch_policies[].name'
```

Expected output for the reconciled environments (`github-pages`, `apko-lock`,
`release`, `release-tags`, `image-push`):

- `deployment_branch_policy`: `{"protected_branches": false, "custom_branch_policies": true}`
- `branch_policies` for `github-pages`, `apko-lock`, `release`: `["main"]`
- `branch_policies` for `release-tags`: `["v*"]`
- `branch_policies` for `image-push`: `["main", "v*"]`

`cloudflare-preview` and `atlas` are intentionally excluded from the
`custom_branch_policies` expectation -- see the rationale above.

## Required secrets

Secrets gated by deployment environments are only available to jobs whose
`github.ref` matches that environment's branch policy. Any job referencing
`secrets.<NAME>` in its `env:` or step inputs must run under the
environment that scopes the secret.

### `RELEASE_BOT_APP_*`

The release pipeline is authenticated by a dedicated GitHub App,
`synthorg-release-bot`. Its credentials live in the `release`
deployment environment as two secrets:

- `RELEASE_BOT_APP_ID` -- the numeric App ID shown on the App's
  settings page.
- `RELEASE_BOT_APP_PRIVATE_KEY` -- the full `.pem` contents verbatim,
  including the opening and closing marker lines. Both markers must
  be present and spelled exactly as emitted by the GitHub App page:
  - Opening line: `-----BEGIN RSA PRIVATE KEY-----`
  - Closing line: `-----END RSA PRIVATE KEY-----`
  Paste the file contents exactly as downloaded -- GitHub's secret
  store accepts multi-line values but silently strips trailing
  whitespace, so do not hand-edit the `.pem`.

**Why an App and not a PAT.** The prior implementation used a
fine-grained PAT (`RELEASE_PLEASE_TOKEN`). PATs produce **unsigned**
API commits -- the `required_signatures` rule on `main` rejects
them. The only identities that yield GitHub-signed API commits are
`GITHUB_TOKEN` and App installation tokens. `GITHUB_TOKEN` cannot
be used here because its pushes are suppressed from firing
downstream workflow events (GitHub's anti-recursion rule). The App
token satisfies both constraints: commits verify as
`{verified: true, reason: "valid"}` AND fire downstream
workflows. See issue #1555 for the incident history.

**Purpose**. Every release workflow mints a fresh short-lived App
installation token (valid ≤1 hour) via the
`release-runner-setup` composite action, which wraps
`actions/create-github-app-token@v3.1.1`. Consumers:

- `release.yml` -- `release-please-action` token input, so the RP
  tag push on release-PR merge triggers Docker + CLI builds. The
  BSL Change Date Contents API commit keeps `GITHUB_TOKEN` (lands
  on the RP PR branch, not `main`; no recursion concern).
- `dev-release.yml` -- tag creation for dev pre-releases via
  `gh api`.
- `auto-rollover.yml` -- empty `Release-As:` commit via the Git
  Data API (`POST /git/commits` + `PATCH /git/refs/heads/main`).
- `graduate.yml` -- user-triggered signed empty commit with a
  `Release-As:` trailer for target versions that skip the normal
  patch cadence.
- `test-signing.yml` -- nightly verification that each of the
  above paths produces a commit with
  `{verified: true, reason: "valid"}`.

**App configuration**. Ship the App with the minimum privilege set:

- Owner: `Aureliolo` (personal account).
- Install scope: `Aureliolo/synthorg` only. Single-repo install
  bounds the blast radius to the intended target.
- Repository permissions:
  - `Contents: Read and write`
  - `Pull requests: Read and write`
  - `Metadata: Read`
- Subscribe to **no** events -- this App has no webhook
  endpoint and does not need to receive events.

**Provisioning checklist** (follow once at setup):

1. Settings -> Developer settings -> GitHub Apps -> New GitHub App.
2. Configure permissions + install scope as above.
3. Generate a private key; download the `.pem`.
4. Install the App on `Aureliolo/synthorg`.
5. Copy the numeric App ID.
6. Repo Settings -> Environments -> `release` -> Environment
   secrets. Add `RELEASE_BOT_APP_ID` (numeric) and
   `RELEASE_BOT_APP_PRIVATE_KEY` (full PEM contents).
7. Confirm the action allowlist includes
   `actions/create-github-app-token@*` (SHA-pinned in-workflow)
   and `actions/ai-inference@*` (used by the release-notes
   Highlights step in `release.yml`).

**Release Please is not being removed.** Only the *credential* it
uses is changing. Release Please still creates release PRs,
generates changelogs, and drafts releases on every push to `main`;
this PR just swaps the long-lived `RELEASE_PLEASE_TOKEN` PAT for
an ephemeral App installation token passed via
`steps.setup.outputs.token` (see `release.yml`). Release Please
itself needs a token -- that requirement does not go away -- it
now receives the App token at job start instead of reading a PAT
from a repo secret.

**Sunset of the prior PAT** (`RELEASE_PLEASE_TOKEN`):

After the first green release cycle under the App, complete the
cutover in two steps:

1. Delete the `RELEASE_PLEASE_TOKEN` secret from repo-level
   Actions secrets (`Settings -> Secrets and variables ->
   Actions`). The `no-release-please-token` pre-commit hook
   prevents reintroduction at commit time, but removing the
   secret value forces an immediate, visible failure if any
   workflow ever tries to reference it again.
2. Revoke the underlying fine-grained PAT on GitHub
   (`Settings -> Developer settings -> Personal access tokens ->
   Fine-grained tokens`). Revocation is irreversible; do this
   step only after step 1 has survived at least one full release
   cycle (stable + dev tag + at least one `auto-rollover` or
   `graduate` invocation).

**No rotation schedule**. Installation tokens are ephemeral --
minted per workflow run and valid for at most one hour, then
discarded. The only long-lived secret is the App private key,
rotated only if the key file is compromised. Private-key rotation
is a two-step: generate a new key in the App settings, replace
`RELEASE_BOT_APP_PRIVATE_KEY` in the `release` environment,
delete the old key.

**Access control**. The `release` environment's branch policy
(`main` only) is the structural gate. A workflow triggered from
any other ref cannot read `RELEASE_BOT_APP_*` even if it
declares them in its YAML. Tag-only release jobs
(`cli.yml:cli-release`, `docker.yml:update-release`) run under
the separate `release-tags` environment, which carries no
privileged secrets, so a forged `v*` tag on unmerged code
cannot reach the App credentials.

## Testing the `apko-lock` gate

Trigger the workflow from a non-main ref via `workflow_dispatch` API (pushing
a commit to a feature branch is not enough -- the workflow is not configured
for `push` events):

```bash
# Trigger from main -- should succeed
gh workflow run apko-lock.yml --ref main

# Trigger from a feature branch -- should be blocked at the environment gate.
# GitHub will show the job in "Waiting" state; the run log cites the branch
# policy violation.
gh workflow run apko-lock.yml --ref chore/some-branch
```
