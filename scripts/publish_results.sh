#!/usr/bin/env bash
# Publish one successful run as a separate immutable results/<run_id> branch.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="${1:-$(find "$ROOT/runs" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)}"
[[ -d "$RUN_DIR" && -s "$RUN_DIR/metrics.csv" && -s "$RUN_DIR/summary.json" ]] || {
  echo "No completed run: $RUN_DIR" >&2; exit 2;
}
RUN_NAME="$(basename "$RUN_DIR")"
[[ "$RUN_NAME" =~ ^[A-Za-z0-9_.-]+$ ]] || exit 2
BRANCH="results/$RUN_NAME"
KEY="${FC_DEPLOY_KEY:-$HOME/.ssh/id_ed25519_fc_memory_lab}"
[[ -f "$KEY" ]] || { echo "Missing deploy private key. Run scripts/setup_ssh.sh" >&2; exit 2; }
git remote get-url origin >/dev/null || { echo 'Missing origin remote' >&2; exit 2; }
[[ "$(git remote get-url origin)" == git@github.com:* ]] || {
  echo 'Set origin to git@github.com:OWNER/REPO.git before using deploy key.' >&2; exit 2;
}
WORKTREE="$(mktemp -d)"
cleanup() { cd "$ROOT"; git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true; rmdir "$WORKTREE" 2>/dev/null || true; }
trap cleanup EXIT
git worktree add --detach "$WORKTREE" HEAD >/dev/null
cd "$WORKTREE"
git switch -c "$BRANCH"
mkdir -p "results/$RUN_NAME"
for file in metrics.csv summary.json metadata.json validation.json guest-console.log firecracker.log; do
  if [[ -f "$RUN_DIR/$file" ]]; then
    cp "$RUN_DIR/$file" "results/$RUN_NAME/$file"
  fi
done
[[ -s "results/$RUN_NAME/metadata.json" ]] || { echo 'Missing metadata' >&2; exit 2; }
git add -f "results/$RUN_NAME"
git -c user.name='Firecracker Experiment' -c user.email='fc-memory-lab@users.noreply.github.com' \
  commit -m "results: $RUN_NAME"
GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes" git push --set-upstream origin "$BRANCH"
printf '\nPublished: %s\n' "$BRANCH"
