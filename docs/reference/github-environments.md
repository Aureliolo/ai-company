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
| `release` | `main` | `release.yml` + `dev-release.yml` (main pushes), `finalize-release.yml:publish` (workflow_run resolves `github.ref` to main). Holds `RELEASE_PLEASE_TOKEN`. |
| `release-tags` | `v*` | `cli.yml:cli-release` + `docker.yml:update-release` (v* tag pushes). Structural ref gate only; no privileged secrets. |
| `image-push` | `main`, `v*` | `docker.yml` `*-publish` jobs (4 apko base pushes + 5 app image pushes) on main and v* refs |
| `apko-lock` | `main` | `apko-lock.yml` schedule + workflow_dispatch |
| `cloudflare-preview` | _none_ (see below) | `pages-preview.yml` pull_request events |
| `atlas` | _none_ (see below) | `ci.yml:schema-validate` push + pull_request |

The release path is intentionally split into two environments. GitHub's
deployment branch policies only match ref *names* -- they do NOT verify
that a tag's commit is reachable from an allowed branch. Admitting `v*`
on the secret-bearing environment would let any `v`-prefixed tag
(including one forged on an unmerged feature branch) unlock
`RELEASE_PLEASE_TOKEN`. Keeping `release` main-only and routing tag-only
jobs through `release-tags` preserves the structural ref gate without
exposing the PAT.

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

### `RELEASE_PLEASE_TOKEN`

A GitHub Personal Access Token consumed by the release pipeline. Scoped
under the `release` deployment environment.

**Purpose**:

- `release.yml` uses it for the pre-tag creation step, the
  `googleapis/release-please-action` step, the Release PR branch checkout,
  and the BSL Change Date `git push`. Each of those steps writes to the
  repository state (tags, release PR, commits) on behalf of the release
  bot.
- `dev-release.yml` uses it to create dev pre-release tags (e.g.
  `v0.7.2-dev.3`). Unlike the default `GITHUB_TOKEN`, a PAT-authored tag
  push triggers downstream workflows (docker.yml, cli.yml, etc.), which is
  the intended behavior -- dev tags must run through the same build-sign-
  attest pipeline as stable releases.

**Required PAT scopes** (fine-grained is strongly preferred):

- **Fine-grained PAT (preferred)**: scope to the `Aureliolo/synthorg`
  repository only, with these repository permissions:
  - `Contents: Read and write`
  - `Pull requests: Read and write`
  - `Metadata: Read`
- **Classic PAT (discouraged)**: requires the `repo` scope, which grants
  full control of **all** private repositories the owner can access --
  there is no way to narrow it to a single repo. Only use a classic PAT
  if your org restricts fine-grained PATs. No org scopes (`admin:org`,
  `admin:public_key`, `write:packages`, etc.) -- keep the blast radius at
  repository-level authority.

The token must NOT carry organization-level permissions. If this repo ever
moves under an organization, revoke and re-issue a fine-grained token
scoped to the new repo path rather than granting org admin.

**Rotation**:

- Expiry is owner-tracked; set a calendar reminder 30 days before the PAT
  expiration.
- `RELEASE_PLEASE_TOKEN` is scoped to the `release` **deployment
  environment**, not the repo-level Actions secret store. Rotate via repo
  Settings > Environments > `release` > Environment secrets > click
  `RELEASE_PLEASE_TOKEN` > update secret. Updating the repo-level Actions
  secret of the same name has no effect on the gated release jobs.
- The old token remains valid until its expiry date even after updating
  the environment secret; revoke the old PAT from the PAT owner's GitHub
  settings to close the window.

**Access control**: the `release` environment's branch policy (`main`
only) is the structural gate. A workflow triggered from any other ref
cannot read the secret even if it declares `secrets.RELEASE_PLEASE_TOKEN`
in its YAML. Tag-only release jobs (`cli.yml:cli-release`,
`docker.yml:update-release`) deliberately run under the separate
`release-tags` environment, which carries no privileged secrets, so a
forged `v*` tag on unmerged code cannot unlock the PAT.

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
