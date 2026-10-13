#!/usr/bin/env bash
# Sequentially test baseline, balloon and reporting. No concurrent VMs.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PUBLISH=0
REPEATS=1
while (($#)); do
  case "$1" in
    --publish) PUBLISH=1; shift ;;
    --repeats) [[ $# -ge 2 ]] || exit 2; REPEATS="$2"; shift 2 ;;
    --help) echo "Usage: bash scripts/run_reclaim_suite.sh [--publish] [--repeats N]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$REPEATS" =~ ^[1-5]$ ]] || { echo 'Select between 1 and 5 repeats' >&2; exit 2; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "Tracked changes present; commit them before benchmarking" >&2; exit 2;
}
[[ "$(git branch --show-current)" == exp/reclaim-cost-workload ]] || {
  echo "Switch to exp/reclaim-cost-workload first" >&2; exit 2;
}
mkdir -p runs
for ((trial=1;trial<=REPEATS;trial++)); do
  for mode in baseline balloon reporting; do
    echo "=== $mode / repetition $trial of $REPEATS ==="
    cfg="$(mktemp)"
    case "$mode" in
      reporting) reporting=true;;
      *) reporting=false;;
    esac
    printf 'MODE=%s\nMEMORY_MIB=1024\nBALLOON_MIB=512\nFREE_PAGE_REPORTING=%s\n' \
      "$mode" "$reporting" > "$cfg"
    before="$(find runs -mindepth 1 -maxdepth 1 -type d -name "*-$mode-*" | sort | tail -1)"
    if ./scripts/run.sh "$cfg"; then
      rm -f "$cfg"
    else
      status=$?
      rm -f "$cfg"
      echo "Run failed; isolated guest disk and logs kept for debugging." >&2
      exit "$status"
    fi
    latest="$(find runs -mindepth 1 -maxdepth 1 -type d -name "*-$mode-*" | sort | tail -1)"
    [[ -n "$latest" && "$latest" != "$before" && -s "$latest/reclaim.json" ]] || {
      echo "Could not identify complete new run" >&2; exit 3;
    }
    if (( PUBLISH )); then
      ./scripts/publish_results.sh "$latest"
    fi
    rm -f -- "$latest/guest.ext4"
  done
done
echo "All selected experiments completed; metrics remain under runs/"
