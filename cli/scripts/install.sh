#!/usr/bin/env bash
# SynthOrg CLI installer for Linux and macOS.
# Usage: curl -sSfL https://raw.githubusercontent.com/Aureliolo/synthorg/main/cli/scripts/install.sh | sh
#
# Environment variables:
#   SYNTHORG_VERSION  — specific version to install (default: latest)
#   INSTALL_DIR       — installation directory (default: /usr/local/bin)

set -euo pipefail

REPO="Aureliolo/synthorg"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
BINARY_NAME="synthorg"

# --- Detect platform ---

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
    x86_64|amd64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

case "$OS" in
    linux|darwin) ;;
    *) echo "Unsupported OS: $OS (use install.ps1 for Windows)"; exit 1 ;;
esac

# --- Resolve version ---

if [ -z "${SYNTHORG_VERSION:-}" ]; then
    echo "Fetching latest release..."
    SYNTHORG_VERSION="$(curl -sSf "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name"' | cut -d '"' -f 4)"
fi

VERSION_NO_V="${SYNTHORG_VERSION#v}"
echo "Installing SynthOrg CLI ${SYNTHORG_VERSION}..."

# --- Download ---

ARCHIVE_NAME="synthorg_${OS}_${ARCH}.tar.gz"
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${SYNTHORG_VERSION}/${ARCHIVE_NAME}"
CHECKSUMS_URL="https://github.com/${REPO}/releases/download/${SYNTHORG_VERSION}/checksums.txt"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Downloading ${DOWNLOAD_URL}..."
curl -sSfL -o "${TMP_DIR}/${ARCHIVE_NAME}" "$DOWNLOAD_URL"
curl -sSfL -o "${TMP_DIR}/checksums.txt" "$CHECKSUMS_URL"

# --- Verify checksum ---

echo "Verifying checksum..."
cd "$TMP_DIR"

if command -v sha256sum >/dev/null 2>&1; then
    grep "$ARCHIVE_NAME" checksums.txt | sha256sum -c --quiet
elif command -v shasum >/dev/null 2>&1; then
    grep "$ARCHIVE_NAME" checksums.txt | shasum -a 256 -c --quiet
else
    echo "Warning: no sha256sum or shasum available — skipping checksum verification"
fi

# --- Extract and install ---

echo "Extracting..."
tar -xzf "$ARCHIVE_NAME"

echo "Installing to ${INSTALL_DIR}/${BINARY_NAME}..."
if [ -w "$INSTALL_DIR" ]; then
    mv "$BINARY_NAME" "${INSTALL_DIR}/${BINARY_NAME}"
else
    sudo mv "$BINARY_NAME" "${INSTALL_DIR}/${BINARY_NAME}"
fi
chmod +x "${INSTALL_DIR}/${BINARY_NAME}"

echo ""
"${INSTALL_DIR}/${BINARY_NAME}" version
echo ""
echo "SynthOrg CLI installed successfully. Run 'synthorg init' to get started."
