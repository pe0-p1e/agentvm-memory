#!/usr/bin/env bash
# Publish one successful run as a separate immutable results/<run_id> branch.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="${1:-$(find "$ROOT/runs" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)}"
[[ -d "$RUN_DIR" && -s "$RUN_DIR/metrics.csv" && -s "$RUN_DIR/summary.json" ]] || {
  echo "No completed run: $RUN_DIR" >&2; exit 2;
}
# Normalize BEFORE switching to a temporary Git worktree; the suite passes a
# path relative to the original repository, which is otherwise invalid there.
RUN_DIR="$(realpath -e -- "$RUN_DIR")"
[[ "$RUN_DIR" == "$ROOT/runs/"* ]] || {
  echo "Refusing to publish a directory outside $ROOT/runs" >&2; exit 2;
}
[[ -s "$RUN_DIR/metadata.json" && -s "$RUN_DIR/validation.json" ]] || {
  echo "Incomplete run: required metadata.json or validation.json missing" >&2; exit 2;
}
RUN_NAME="$(basename "$RUN_DIR")"
[[ "$RUN_NAME" =~ ^[A-Za-z0-9_.-]+$ ]] || exit 2
BRANCH="results/$RUN_NAME"
# SSH deploy key is supported, but blocked SSH networks can push over HTTPS.
# For HTTPS: authenticate with Git Credential Manager, gh auth login, or a PAT
# entered interactively as the Git password. Never embed tokens in Git URLs.
KEY="${FC_DEPLOY_KEY:-$HOME/.ssh/id_ed25519_fc_memory_lab}"
ORIGIN_URL="$(git remote get-url origin)" || { echo 'Missing origin remote' >&2; exit 2; }
case "$ORIGIN_URL" in
  git@github.com:*|ssh://git@github.com/*)
    [[ -f "$KEY" ]] || { echo "Missing SSH key: $KEY" >&2; exit 2; }
    export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes"
    ;;
  https://github.com/*)
    unset GIT_SSH_COMMAND || true
    ;;
  *)
    echo "Unsupported origin URL: $ORIGIN_URL. Use a GitHub HTTPS or SSH origin." >&2
    exit 2
    ;;
esac
WORKTREE="$(mktemp -d)"
cleanup() { cd "$ROOT"; git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true; rmdir "$WORKTREE" 2>/dev/null || true; }
trap cleanup EXIT
git worktree add --detach "$WORKTREE" HEAD >/dev/null
cd "$WORKTREE"
# Commit on detached HEAD. This avoids leaving behind a local results branch
# after a failed upload and permits safe retries of completed runs.
mkdir -p "results/$RUN_NAME"
for file in metrics.csv summary.json metadata.json validation.json reclaim.json host-events.jsonl guest-console.log firecracker.log; do
  if [[ -f "$RUN_DIR/$file" ]]; then
    cp "$RUN_DIR/$file" "results/$RUN_NAME/$file"
  fi
done
[[ -s "results/$RUN_NAME/metadata.json" ]] || { echo 'Missing metadata' >&2; exit 2; }
git add -f "results/$RUN_NAME"
git -c user.name='Firecracker Experiment' -c user.email='fc-memory-lab@users.noreply.github.com' \
  commit -m "results: $RUN_NAME"
# Push retries cope with intermittent Mihomo / ssh.github.com:443 disconnects.
# The same local commit is retried; completed VM data is never re-executed.
RETRIES="${PUBLISH_RETRIES:-4}"
[[ "$RETRIES" =~ ^[1-6]$ ]] || { echo 'PUBLISH_RETRIES must be 1..6' >&2; exit 2; }
published=0
for ((attempt=1; attempt<=RETRIES; attempt++)); do
  if git push origin "HEAD:refs/heads/$BRANCH"; then
    published=1
    break
  fi
  echo "GitHub upload attempt $attempt/$RETRIES failed for $BRANCH." >&2
  if (( attempt < RETRIES )); then sleep $((attempt * 3)); fi
done
if (( ! published )); then
  echo "Upload deferred. Original results remain at $RUN_DIR" >&2
  exit 1
fi
printf '\nPublished: %s\n' "$BRANCH"
