#!/usr/bin/env bash
# Sequential experiments across real Git branches; never runs concurrently.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PUBLISH=false
if [[ "${1:-}" == '--publish' ]]; then PUBLISH=true; fi
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo 'Commit tracked changes first.' >&2; exit 2; }
ORIGINAL="$(git branch --show-current)"
restore() { git switch "$ORIGINAL" >/dev/null || true; }
trap restore EXIT
for branch in main exp/balloon exp/free-page-reporting; do
  echo "=== EXPERIMENT BRANCH: $branch ==="
  git switch "$branch"
  ./scripts/run.sh
  latest="$(find "$ROOT/runs" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
  if "$PUBLISH"; then
    ./scripts/publish_results.sh "$latest"
  fi
done
printf '\nAll experiment branches completed successfully.\n'
