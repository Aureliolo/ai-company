#!/usr/bin/env bash
# Install the external Go toolchain required for local CLI development.
#
# golangci-lint is intentionally NOT declared as a `tool` directive in cli/go.mod:
# it is GPL-3.0, and the `tool` directive would pull ~170 GPL-licensed transitive
# packages into the module graph, conflicting with the project's BUSL-1.1 license
# and blocking the BUSL -> Apache-2.0 conversion.
#
# CI installs golangci-lint via the official GitHub Action
# (.github/workflows/cli.yml uses golangci/golangci-lint-action). Local developers
# run this script once per machine. Renovate tracks the pinned version via the
# "go install binary versions" custom regex manager in renovate.json.

set -euo pipefail

if ! command -v go >/dev/null 2>&1; then
  echo "error: go is not installed or not on PATH" >&2
  exit 1
fi

echo "Installing golangci-lint..."
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.11.4

if ! command -v golangci-lint >/dev/null 2>&1; then
  echo "error: golangci-lint installed but not on PATH -- ensure \$(go env GOPATH)/bin is on PATH" >&2
  exit 1
fi

echo "golangci-lint ready: $(golangci-lint --version 2>&1 | head -n1)"
