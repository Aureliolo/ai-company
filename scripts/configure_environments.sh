#!/usr/bin/env bash
# Configure GitHub deployment environment branch policies for SynthOrg.
#
# GitHub environments gate workflow jobs that reference them. Each environment
# below has a branch allowlist so the job only runs when the deployment ref
# matches an expected pattern. Environment-level policies cannot be expressed
# in workflow YAML; they must be applied via the REST API (or the UI).
#
# This script is a reconciler: re-running with --apply is safe. Environments
# are created if they do not exist, and each environment's branch-policy set is
# driven exclusively by ENV_CONFIG below -- policies not listed there are
# removed so the applied state exactly matches the desired state. A POST that
# races a concurrent run (HTTP 422 "already exists") is treated as an
# idempotent no-op.
#
# Usage:
#   scripts/configure_environments.sh                 # dry-run (default)
#   scripts/configure_environments.sh --apply         # apply changes
#   scripts/configure_environments.sh --apply --repo owner/name
#
# Prerequisites:
#   - gh CLI authenticated with the `repo` scope (sufficient for all four
#     environments / deployment-branch-policies endpoints per GitHub's docs;
#     fine-grained PATs need `administration:write`)
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
      sed -n '2,25p' "$0"
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
  "release|main,v*"
  "apko-lock|main"
  "image-push|main,v*"
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

# Like run_gh, but reports whether the request hit the "already exists" no-op
# path. Exit codes:
#   0  -- request succeeded (real create/update/delete)
#   2  -- request returned HTTP 422 (no-op: the resource already matched)
#   1  -- any other failure; stderr is forwarded to the user
run_gh_allow_422() {
  if [ "$MODE" = "apply" ]; then
    local err
    err=$(gh api "$@" 2>&1 >/dev/null) && return 0
    if printf '%s' "$err" | grep -q 'HTTP 422'; then
      return 2
    fi
    printf '%s\n' "$err" >&2
    return 1
  else
    printf '  [dry-run] gh api'
    for arg in "$@"; do printf ' %q' "$arg"; done
    printf '\n'
    return 0
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

# Prints `name<TAB>id` for each current branch policy on the environment.
# The GitHub DELETE endpoint requires the numeric id, not the name.
list_branch_policies() {
  local env_name="$1"
  # Apply AND dry-run both issue this read-only GET so the reconciler has a
  # real picture of which policies would be added or removed. A missing
  # environment (first run) comes back as HTTP 404; translate that to "no
  # policies exist yet" rather than aborting. --jq filters inside gh so we do
  # not shell out to a separate jq dependency. The `if !` form disables errexit
  # for this single command so `rc=$?` logic is actually reached on failure --
  # a bare `out=$(...)` + `rc=$?` would exit before the handler runs.
  local out
  if ! out=$(gh api "repos/${REPO}/environments/${env_name}/deployment-branch-policies" \
    --jq '.branch_policies[] | "\(.name)\t\(.id)"' 2>&1); then
    if printf '%s' "$out" | grep -q 'HTTP 404'; then
      return 0
    fi
    printf '%s\n' "$out" >&2
    return 1
  fi
  printf '%s' "$out"
}

add_branch_policy() {
  local env_name="$1"
  local pattern="$2"
  local rc
  # A racing concurrent run (or a stale list) can make the POST return 422
  # "already exists"; treat that as idempotent success via run_gh_allow_422's
  # exit-2 signal. Wrap the call in an `if` so errexit does not fire before
  # we can inspect $?.
  if run_gh_allow_422 --method POST "repos/${REPO}/environments/${env_name}/deployment-branch-policies" \
    -f "name=${pattern}" -f "type=branch"; then
    rc=0
  else
    rc=$?
  fi
  case "$rc:$MODE" in
    0:apply) echo "  policy '${pattern}' added" ;;
    2:apply) echo "  policy '${pattern}' already present (422 no-op)" ;;
    0:dry-run) echo "  policy '${pattern}' to add" ;;
    *) return "$rc" ;;
  esac
}

delete_branch_policy() {
  local env_name="$1"
  local pattern="$2"
  local policy_id="$3"
  if [ -z "$policy_id" ]; then
    echo "error: delete_branch_policy: missing id for '${pattern}'" >&2
    return 1
  fi
  run_gh --method DELETE "repos/${REPO}/environments/${env_name}/deployment-branch-policies/${policy_id}"
  if [ "$MODE" = "apply" ]; then
    echo "  policy '${pattern}' removed (not in desired set)"
  else
    echo "  policy '${pattern}' to remove (not in desired set)"
  fi
}

# Reconciles the environment's branch policies against the desired CSV list:
# creates any missing pattern (idempotent via 422 tolerance) and deletes any
# pattern that is present but not in the desired set.
reconcile_policies() {
  local env_name="$1"
  local desired_csv="$2"
  local current name id pat
  local -a desired_patterns=()
  IFS=',' read -ra desired_patterns <<< "$desired_csv"

  if ! current=$(list_branch_policies "$env_name"); then
    echo "error: failed to list branch policies for '${env_name}'" >&2
    return 1
  fi

  # Create missing.
  for pat in "${desired_patterns[@]}"; do
    if printf '%s\n' "$current" | awk -F'\t' '{print $1}' | grep -qxF -- "$pat"; then
      echo "  policy '${pat}' already present"
    else
      add_branch_policy "$env_name" "$pat"
    fi
  done

  # Remove extras. Skip if list is empty (first run / dry-run with no env yet).
  [ -z "$current" ] && return 0
  while IFS=$'\t' read -r name id; do
    [ -z "$name" ] && continue
    if ! printf '%s\n' "${desired_patterns[@]}" | grep -qxF -- "$name"; then
      delete_branch_policy "$env_name" "$name" "$id"
    fi
  done <<< "$current"
}

for row in "${ENV_CONFIG[@]}"; do
  env_name="${row%%|*}"
  patterns="${row#*|}"
  ensure_environment "$env_name"
  reconcile_policies "$env_name" "$patterns"
  echo
done

if [ "$MODE" = "dry-run" ]; then
  echo "Dry-run complete. Re-run with --apply to perform the above changes."
fi
