#!/usr/bin/env bash
# One-time bootstrap after an EMPTY GitHub repo exists and a deploy key is added.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REPO="${1:-pe0-p1e/agentvm-memory}"
[[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || exit 2
KEY="${FC_DEPLOY_KEY:-$HOME/.ssh/id_ed25519_fc_memory_lab}"
[[ -f "$KEY" ]] || { echo 'Run ./scripts/setup_ssh.sh and add the PUBLIC deploy key first.' >&2; exit 2; }
git remote set-url origin "git@github.com:$REPO.git"
for branch in main exp/balloon exp/free-page-reporting; do
  if ! git show-ref --verify --quiet "refs/heads/$branch"; then
    git branch "$branch" "refs/remotes/origin/$branch"
  fi
done
GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes" \
  git push -u origin main exp/balloon exp/free-page-reporting
printf '\nPublished project and three source branches to https://github.com/%s\n' "$REPO"
