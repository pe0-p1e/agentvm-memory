#!/usr/bin/env bash
# Installs only the upstream AENV CLI into the current user's ~/.local/bin.
# Does not install/start/restart AgentENV server or touch shared containers.
set -Eeuo pipefail
if (( EUID == 0 )); then
  echo "Run as your normal user, not root." >&2; exit 2
fi
for dep in curl jq tar gzip sha256sum; do
  if ! command -v "$dep" >/dev/null 2>&1; then
    echo "Missing $dep. Ask the lab administrator to provide it or install it in your user environment." >&2
    echo "Refusing to invoke the upstream installer, which may use sudo to install missing dependencies." >&2
    exit 2
  fi
done
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
url="https://raw.githubusercontent.com/kvcache-ai/AgentENV/main/scripts/install-cli.sh"
echo "Downloading official CLI installer from $url"
curl -fsSL --retry 3 --max-time 90 "$url" -o "$tmp/install-cli.sh"
# Official upstream installer downloads signed release metadata and verifies asset SHA256.
INSTALL_DIR="$INSTALL_DIR" bash "$tmp/install-cli.sh"
export PATH="$INSTALL_DIR:$PATH"
"$INSTALL_DIR/aenv" --help >/dev/null
echo "AENV CLI installed for this user: $INSTALL_DIR/aenv"
echo "Next: obtain an authorized endpoint and API key from the lab owner, then run: aenv auth"
