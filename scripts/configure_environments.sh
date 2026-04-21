#!/usr/bin/env bash
# Configure GitHub deployment environment branch policies for SynthOrg.
#
# GitHub environments gate workflow jobs that reference them. Each environment
# below has a branch allowlist so the job only runs when the deployment ref
# matches an expected pattern. Environment-level policies cannot be expressed
# in workflow YAML; they must be applied via the REST API (or the UI).
#
# This script is idempotent: re-running with --apply is safe. Environments are
# created if they do not exist, and branch policies are looked up by name before
# being added (POST to an existing name returns 422; the script treats that as a
# no-op success).
#
# Usage:
#   scripts/configure_environments.sh                 # dry-run (default)
#   scripts/configure_environments.sh --apply         # apply changes
#   scripts/configure_environments.sh --apply --repo owner/name
#
# Prerequisites:
#   - gh CLI authenticated with admin:repo_hook and repo scopes
#   - default repo inferred via `gh repo view`, or pass --repo owner/name

set -euo pipefail

MODE="dry-run"
REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift ;;
    --apply) MODE="apply"; shift ;;
    --repo)
      # Guard $2 access so `--repo` with no value does not crash on set -u.
      if [ $# -lt 2 ] || [ -z "${2-}" ]; then
        echo "error: --repo requires owner/name" >&2
        exit 2
      fi
      REPO="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,22p' "$0"
      exit 0
      ;;
    *) echo "error: unknown flag: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
fi
if [ -z "$REPO" ]; then
  echo "error: could not infer repo -- pass --repo owner/name" >&2
  exit 2
fi

echo "Target repo: ${REPO}"
echo "Mode: ${MODE}"
echo

# Environment configuration table: ENV_NAME|BRANCH_PATTERN[,BRANCH_PATTERN...]
# Patterns follow GitHub's deployment-branch-policies semantics, which only
# match refs/heads/* and refs/tags/* (NOT refs/pull/*). For PR-triggered envs
# (cloudflare-preview, atlas) the workflow-level `if:` guard is the actual
# gate -- see docs/reference/github-environments.md for rationale.
ENV_CONFIG=(
  "github-pages|main"
  "release|main"
  "apko-lock|main"
)

run_gh() {
  if [ "$MODE" = "apply" ]; then
    gh api "$@" >/dev/null
  else
    printf '  [dry-run] gh api'
    for arg in "$@"; do printf ' %q' "$arg"; done
    printf '\n'
  fi
}

# Like run_gh, but tolerates HTTP 422 (conflict on an existing resource) as a
# no-op success. Used for endpoints where the idempotent path is "POST already
# exists => swallow the error". Captures stderr so we can inspect the status.
run_gh_allow_422() {
  if [ "$MODE" = "apply" ]; then
    local err
    err=$(gh api "$@" 2>&1 >/dev/null) && return 0
    if printf '%s' "$err" | grep -q 'HTTP 422'; then
      return 0
    fi
    printf '%s\n' "$err" >&2
    return 1
  else
    printf '  [dry-run] gh api'
    for arg in "$@"; do printf ' %q' "$arg"; done
    printf '\n'
  fi
}

ensure_environment() {
  local env_name="$1"
  echo "==> ${env_name}"
  # PUT is idempotent: creates or updates the environment with branch-policy enabled.
  run_gh --method PUT "repos/${REPO}/environments/${env_name}" \
    -f 'deployment_branch_policy[protected_branches]=false' \
    -f 'deployment_branch_policy[custom_branch_policies]=true'
}

list_branch_policies() {
  local env_name="$1"
  if [ "$MODE" = "apply" ]; then
    gh api "repos/${REPO}/environments/${env_name}/deployment-branch-policies" \
      --jq '.branch_policies[].name' 2>/dev/null || echo ""
  else
    # In dry-run we pretend no policies exist so every pattern shows as "to add".
    echo ""
  fi
}

add_branch_policy() {
  local env_name="$1"
  local pattern="$2"
  local existing verb
  existing=$(list_branch_policies "$env_name")
  if echo "$existing" | grep -qxF -- "$pattern"; then
    echo "  policy '${pattern}' already present"
    return 0
  fi
  # A racing concurrent run (or a stale cache in list_branch_policies) can leave
  # the POST returning 422 "already exists"; treat that as idempotent success
  # rather than a hard failure -- the header doc promises re-runs are safe.
  run_gh_allow_422 --method POST "repos/${REPO}/environments/${env_name}/deployment-branch-policies" \
    -f "name=${pattern}" -f "type=branch"
  if [ "$MODE" = "apply" ]; then verb="added"; else verb="to add"; fi
  echo "  policy '${pattern}' ${verb}"
}

for row in "${ENV_CONFIG[@]}"; do
  env_name="${row%%|*}"
  patterns="${row#*|}"
  ensure_environment "$env_name"
  IFS=',' read -ra PATS <<< "$patterns"
  for pat in "${PATS[@]}"; do
    add_branch_policy "$env_name" "$pat"
  done
  echo
done

if [ "$MODE" = "dry-run" ]; then
  echo "Dry-run complete. Re-run with --apply to perform the above changes."
fi
