#!/usr/bin/env bash
# SynthOrg CLI installer for Linux and macOS.
# Usage: curl -sSfL https://synthorg.io/get/install.sh | bash
#
# Environment variables:
#   SYNTHORG_VERSION  -- specific version to install (default: latest)
#   INSTALL_DIR       -- installation directory (default: /usr/local/bin)

set -euo pipefail

REPO="Aureliolo/synthorg"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
BINARY_NAME="synthorg"

# --- Colors (disabled when NO_COLOR is set or output is not a terminal) ---

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD="\033[1m"
    DIM="\033[2m"
    GREEN="\033[38;2;52;211;153m"
    BLUE="\033[38;2;56;189;248m"
    RED="\033[38;2;248;113;113m"
    RESET="\033[0m"
else
    BOLD="" DIM="" GREEN="" BLUE="" RED="" RESET=""
fi

step() { printf "${BLUE}[%s/%s]${RESET} %s\n" "$1" "$2" "$3"; }
ok()   { printf "${GREEN}ok${RESET}\n"; }
fail() { printf "${RED}error: %s${RESET}\n" "$1" >&2; exit 1; }

TOTAL=4

# --- Detect platform ---

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
    x86_64|amd64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) fail "unsupported architecture: $ARCH" ;;
esac

case "$OS" in
    linux|darwin) ;;
    *) fail "unsupported OS: $OS (use install.ps1 for Windows)" ;;
esac

# --- Resolve version ---

if [ -z "${SYNTHORG_VERSION:-}" ]; then
    step 1 $TOTAL "Fetching latest release..."
    API_RESPONSE="$(curl -sSf "https://api.github.com/repos/${REPO}/releases/latest")"
    if command -v jq >/dev/null 2>&1; then
        SYNTHORG_VERSION="$(printf '%s' "$API_RESPONSE" | jq -r '.tag_name')"
    elif command -v python3 >/dev/null 2>&1; then
        SYNTHORG_VERSION="$(printf '%s' "$API_RESPONSE" | python3 -c 'import sys,json; print(json.load(sys.stdin)["tag_name"])')"
    else
        SYNTHORG_VERSION="$(printf '%s' "$API_RESPONSE" | grep '"tag_name"' | cut -d '"' -f 4)"
    fi
else
    step 1 $TOTAL "Using specified version..."
fi

# Validate version string to prevent injection.
if ! echo "$SYNTHORG_VERSION" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
    fail "invalid version string: $SYNTHORG_VERSION"
fi

printf "  ${DIM}Platform:${RESET} %s/%s  ${DIM}Version:${RESET} %s\n" "$OS" "$ARCH" "$SYNTHORG_VERSION"

# --- Download ---

ARCHIVE_NAME="synthorg_${OS}_${ARCH}.tar.gz"
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${SYNTHORG_VERSION}/${ARCHIVE_NAME}"
CHECKSUMS_URL="https://github.com/${REPO}/releases/download/${SYNTHORG_VERSION}/checksums.txt"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

step 2 $TOTAL "Downloading..."
curl -sSfL -o "${TMP_DIR}/${ARCHIVE_NAME}" "$DOWNLOAD_URL"
curl -sSfL -o "${TMP_DIR}/checksums.txt" "$CHECKSUMS_URL"

# --- Verify checksum (mandatory) ---

step 3 $TOTAL "Verifying checksum..."

EXPECTED_CHECKSUM="$(awk -v name="${ARCHIVE_NAME}" '$2 == name { print $1 }' "${TMP_DIR}/checksums.txt")"

if [ -z "$EXPECTED_CHECKSUM" ]; then
    fail "no checksum found for ${ARCHIVE_NAME}"
fi

if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL_CHECKSUM="$(sha256sum "${TMP_DIR}/${ARCHIVE_NAME}" | awk '{ print $1 }')"
elif command -v shasum >/dev/null 2>&1; then
    ACTUAL_CHECKSUM="$(shasum -a 256 "${TMP_DIR}/${ARCHIVE_NAME}" | awk '{ print $1 }')"
else
    fail "sha256sum or shasum is required but not found"
fi

if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]; then
    printf "  ${RED}Expected: %s${RESET}\n" "$EXPECTED_CHECKSUM" >&2
    printf "  ${RED}Actual:   %s${RESET}\n" "$ACTUAL_CHECKSUM" >&2
    fail "checksum mismatch"
fi

# --- Extract and install ---

step 4 $TOTAL "Installing to ${INSTALL_DIR}..."
tar -xzf "${TMP_DIR}/${ARCHIVE_NAME}" -C "$TMP_DIR"

if [ -d "$INSTALL_DIR" ] && [ -w "$INSTALL_DIR" ]; then
    mv "${TMP_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/${BINARY_NAME}"
    chmod +x "${INSTALL_DIR}/${BINARY_NAME}"
elif [ ! -d "$INSTALL_DIR" ] && [ -w "$(dirname "$INSTALL_DIR")" ]; then
    mkdir -p "$INSTALL_DIR"
    mv "${TMP_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/${BINARY_NAME}"
    chmod +x "${INSTALL_DIR}/${BINARY_NAME}"
else
    sudo mkdir -p "$INSTALL_DIR"
    sudo mv "${TMP_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/${BINARY_NAME}"
    sudo chmod +x "${INSTALL_DIR}/${BINARY_NAME}"
fi

# --- Done ---

echo ""
printf "${GREEN}SynthOrg CLI installed${RESET} ${DIM}(%s)${RESET}\n" "$SYNTHORG_VERSION"
echo ""

# Warn if INSTALL_DIR is not in PATH (normalize trailing slash).
case ":${PATH}:" in
    *":${INSTALL_DIR%/}:"*) ;;
    *)
        printf "  ${RED}Warning:${RESET} %s is not in your PATH.\n" "$INSTALL_DIR" >&2
        printf "  Add it: ${BOLD}export PATH=\"%s:\$PATH\"${RESET}\n\n" "$INSTALL_DIR" >&2
        ;;
esac

printf "  ${BLUE}Next:${RESET} ${BOLD}synthorg init${RESET}\n"
echo ""
