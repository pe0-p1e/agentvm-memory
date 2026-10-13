#!/usr/bin/env bash
# Dedicated repo-scoped deploy key: NEVER commit or share its private portion.
set -Eeuo pipefail
KEY="${FC_DEPLOY_KEY:-$HOME/.ssh/id_ed25519_fc_memory_lab}"
mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -f "$KEY" -N '' -C "fc-memory-$(hostname)-deploy" </dev/null
fi
chmod 600 "$KEY"
echo
printf 'Add ONLY this public key to GitHub repo Settings > Deploy keys > Add deploy key; enable Allow write access:\n\n'
cat "$KEY.pub"
echo
printf '\nDo not copy %s (the PRIVATE key) into GitHub or chat.\n' "$KEY"
printf 'Verify GitHub SSH host fingerprint when connecting, using GitHub official documentation.\n'
