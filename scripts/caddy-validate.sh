#!/usr/bin/env bash
set -euo pipefail

# Find caddy binary -- check PATH first, then common install locations.
_user="${USER:-${USERNAME:-$(whoami)}}"
if command -v caddy >/dev/null 2>&1; then
    CADDY=caddy
elif [ -x "/c/Users/${_user}/AppData/Local/Microsoft/WinGet/Packages/CaddyServer.Caddy_Microsoft.Winget.Source_8wekyb3d8bbwe/caddy.exe" ]; then
    CADDY="/c/Users/${_user}/AppData/Local/Microsoft/WinGet/Packages/CaddyServer.Caddy_Microsoft.Winget.Source_8wekyb3d8bbwe/caddy.exe"
elif [ -x "/usr/local/bin/caddy" ]; then
    CADDY=/usr/local/bin/caddy
elif [ -x "/usr/bin/caddy" ]; then
    CADDY=/usr/bin/caddy
else
    echo "ERROR: caddy not found. Install with: winget install CaddyServer.Caddy"
    exit 1
fi

exec "$CADDY" validate --config web/Caddyfile --adapter caddyfile
