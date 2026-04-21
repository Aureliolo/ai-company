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
| `release` | `main` | `release.yml` and `dev-release.yml` push to main |
| `apko-lock` | `main` | `apko-lock.yml` schedule + workflow_dispatch |
| `cloudflare-preview` | _none_ (see below) | `pages-preview.yml` pull_request events |
| `atlas` | _none_ (see below) | `ci.yml:schema-validate` push + pull_request |

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
`gh` CLI authenticated with repo admin scope.

## Verifying policies

```bash
gh api repos/Aureliolo/synthorg/environments/apko-lock \
  --jq '.deployment_branch_policy, .name'
gh api repos/Aureliolo/synthorg/environments/apko-lock/deployment-branch-policies \
  --jq '.branch_policies[].name'
```

Expected output for each of `github-pages`, `release`, `apko-lock`:

- `deployment_branch_policy`: `{"protected_branches": false, "custom_branch_policies": true}`
- `branch_policies`: `["main"]`

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
