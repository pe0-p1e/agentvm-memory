#!/usr/bin/env bash
# Sequentially test baseline, balloon and reporting. No concurrent VMs.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PUBLISH=0
REPEATS=1
MODE_CSV="baseline,balloon,reporting"
while (($#)); do
  case "$1" in
    --publish) PUBLISH=1; shift ;;
    --repeats) [[ $# -ge 2 ]] || exit 2; REPEATS="$2"; shift 2 ;;
    --modes) [[ $# -ge 2 ]] || exit 2; MODE_CSV="$2"; shift 2 ;;
    --help) echo "Usage: bash scripts/run_reclaim_suite.sh [--publish] [--repeats N] [--modes balloon,reporting]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$REPEATS" =~ ^[1-5]$ ]] || { echo 'Select between 1 and 5 repeats' >&2; exit 2; }
IFS=, read -r -a SELECTED_MODES <<< "$MODE_CSV"
(( ${#SELECTED_MODES[@]} >= 1 && ${#SELECTED_MODES[@]} <= 3 )) || exit 2
declare -A MODE_SEEN=()
for mode in "${SELECTED_MODES[@]}"; do
  case "$mode" in baseline|balloon|reporting) ;; *)
    echo "Unsupported mode: $mode" >&2; exit 2 ;;
  esac
  [[ -z "${MODE_SEEN[$mode]:-}" ]] || { echo "Duplicate mode: $mode" >&2; exit 2; }
  MODE_SEEN[$mode]=1
done
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "Tracked changes present; commit them before benchmarking" >&2; exit 2;
}
[[ "$(git branch --show-current)" == exp/reclaim-cost-workload ]] || {
  echo "Switch to exp/reclaim-cost-workload first" >&2; exit 2;
}
mkdir -p runs
BATCH_ID="$(date -u +%Y%m%dT%H%M%SZ)-reclaim-$$"
BATCH_DIR="$ROOT/runs/batches/$BATCH_ID"
mkdir -p "$BATCH_DIR"
MANIFEST="$BATCH_DIR/manifest.jsonl"
: > "$MANIFEST"
printf 'Batch: %s\n' "$BATCH_DIR"
for ((trial=1;trial<=REPEATS;trial++)); do
  # Rotate test order between trials to reduce systematic time-of-day bias.
  for ((position=0;position<${#SELECTED_MODES[@]};position++)); do
    index=$(( (trial - 1 + position) % ${#SELECTED_MODES[@]} ))
    mode="${SELECTED_MODES[$index]}"
    echo "=== $mode / repetition $trial of $REPEATS ==="
    cfg="$(mktemp)"
    case "$mode" in
      reporting) reporting=true;;
      *) reporting=false;;
    esac
    printf 'MODE=%s\nMEMORY_MIB=1024\nBALLOON_MIB=512\nFREE_PAGE_REPORTING=%s\n' \
      "$mode" "$reporting" > "$cfg"
    before="$(find runs -mindepth 1 -maxdepth 1 -type d -name "*-$mode-*" | sort | tail -1)"
    if bash scripts/run.sh "$cfg"; then
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
    # Record successful VM data before attempting any network operations.
    printf '{"trial":%d,"mode":"%s","run_id":"%s"}\n' \
      "$trial" "$mode" "$(basename "$latest")" >> "$MANIFEST"
    python3 scripts/aggregate_reclaim.py "$BATCH_DIR"
    rm -f -- "$latest/guest.ext4"
    if (( PUBLISH )); then
      if ! bash scripts/publish_results.sh "$latest"; then
        echo "WARNING: GitHub upload failed; local $latest and batch manifest are preserved." >&2
        echo "The remaining VM experiments will continue; retry uploads separately." >&2
      fi
    fi
  done
done
echo "All selected experiments completed; metrics remain under runs/"
echo "Batch manifest: $MANIFEST"
echo "Aggregate result: $BATCH_DIR/aggregate.json"
