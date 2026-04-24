#!/usr/bin/env bash
# Audit SynthOrg's branch-protection rulesets against the declarative spec
# at .github/branch_protection.yml.
#
# This script is a read-only diff. It fetches the live rulesets via
# `gh api`, normalises them to the same shape as the YAML spec (strips
# volatile fields, sorts rules by type), then diffs. Exits 0 on match,
# 1 on drift with a unified diff printed to stderr.
#
# There is NO --apply mode deliberately: rulesets carry admin-level
# authority, and imperative drift-correction from CI widens the blast
# radius of any one bug in this script. Ruleset edits should continue
# to go through Settings -> Rules in the GitHub UI; this audit simply
# flags when the committed spec and the live state disagree.
#
# Usage:
#   scripts/audit_branch_protection.sh [--repo owner/name]
#
# Requirements:
#   - gh CLI authenticated with `administration:read` (fine-grained PAT)
#     or `repo` (classic PAT).
#   - jq >= 1.6 and yq (Mike Farah's Go yq) >= 4.0 on PATH.
#
# Follow-up: promote this from CI continue-on-error to blocking once
# the spec has survived 30 days of zero-drift runs (tracked in the
# initial PR #1555).

set -euo pipefail

REPO=""
SPEC_FILE=".github/branch_protection.yml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      if [ $# -lt 2 ] || [ -z "${2-}" ]; then
        echo "error: --repo requires owner/name" >&2
        exit 2
      fi
      REPO="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *)
      echo "error: unknown flag: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
fi
if [ -z "$REPO" ]; then
  echo "error: could not infer repo -- pass --repo owner/name" >&2
  exit 2
fi

if [ ! -f "$SPEC_FILE" ]; then
  echo "error: spec file not found: $SPEC_FILE" >&2
  exit 2
fi

command -v gh >/dev/null 2>&1 || { echo "error: gh CLI required" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "error: jq required" >&2; exit 2; }
command -v yq >/dev/null 2>&1 || { echo "error: yq (Mike Farah) required" >&2; exit 2; }

echo "Target repo: ${REPO}"
echo "Spec file:   ${SPEC_FILE}"
echo

# Shared jq filter that normalises a ruleset JSON blob (either from the
# API or from yq's YAML -> JSON conversion) into the canonical shape:
#   - Strip id, node_id, created_at, updated_at, bypass_actors,
#     current_user_can_bypass, source, source_type, _links, node_id
#   - Sort .rules by .type (ascending) so diff is order-independent
#   - Remove null `parameters` objects (YAML spec omits; API may emit)
#
# The filter is applied to a top-level `{rulesets: [...]}` document so
# both sides can share it.
NORMALISE_FILTER='
  def strip_meta:
    del(.id, .node_id, .created_at, .updated_at,
        .bypass_actors, .current_user_can_bypass,
        .source, .source_type, ._links);
  def sort_rules:
    if .rules then .rules |= sort_by(.type) else . end;
  def drop_null_params:
    if .rules then .rules |= map(if has("parameters") and .parameters == null then del(.parameters) else . end) else . end;
  {
    rulesets: (.rulesets | map(strip_meta | sort_rules | drop_null_params) | sort_by(.name))
  }
'

# 1. Compute the canonical live-state JSON.
LIVE_TMP=$(mktemp)
trap 'rm -f "$LIVE_TMP" "$SPEC_TMP"' EXIT
SPEC_TMP=$(mktemp)

IDS=$(gh api "repos/${REPO}/rulesets" --paginate --jq '.[].id')
{
  printf '{"rulesets":['
  first=1
  while read -r id; do
    [ -z "$id" ] && continue
    if [ "$first" -eq 1 ]; then first=0; else printf ','; fi
    gh api "repos/${REPO}/rulesets/${id}"
  done <<< "$IDS"
  printf ']}'
} | jq "$NORMALISE_FILTER" > "$LIVE_TMP"

# 2. Compute the canonical spec JSON. yq converts YAML to JSON then jq
#    applies the same filter.
yq -o=json '.' "$SPEC_FILE" | jq "$NORMALISE_FILTER" > "$SPEC_TMP"

# 3. Diff. diff -u keeps the output compact + anchored.
if diff -u "$SPEC_TMP" "$LIVE_TMP" >/dev/null; then
  echo "OK: live rulesets match ${SPEC_FILE}"
  exit 0
fi

echo "Drift detected between ${SPEC_FILE} and live rulesets on ${REPO}:"
echo
diff -u "$SPEC_TMP" "$LIVE_TMP" || true
echo
echo "Reconcile by editing Settings -> Rules in the GitHub UI, or by"
echo "updating ${SPEC_FILE} if the change is intentional. This audit"
echo "does not auto-apply -- ruleset edits require a human."
exit 1
