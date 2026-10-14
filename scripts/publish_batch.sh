#!/usr/bin/env bash
# Retry publication of already completed experiments; never boots a VM.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BATCH_DIR="\${1:-$(find "$ROOT/runs/batches" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)}"
[[ -n "$BATCH_DIR" && -s "$BATCH_DIR/manifest.jsonl" ]] || {
  echo "Usage: bash scripts/publish_batch.sh <runs/batches/BATCH_ID>" >&2; exit 2;
}
BATCH_DIR="$(realpath -e -- "$BATCH_DIR")"
[[ "$BATCH_DIR" == "$ROOT/runs/batches/"* ]] || {
  echo "Refusing batch outside this repository's runs/batches directory" >&2; exit 2;
}
names="$(mktemp)"
trap 'rm -f -- "$names"' EXIT
python3 - "$BATCH_DIR/manifest.jsonl" > "$names" <<'PY'
import json, re, sys
entries=[json.loads(x) for x in open(sys.argv[1]) if x.strip()]
if not entries:
    raise SystemExit("No completed runs in manifest")
for row in entries:
    name=row["run_id"]
    if not re.fullmatch(r"20[0-9]{6}T[0-9]{6}Z-(baseline|balloon|reporting)-[0-9]+", name):
        raise SystemExit("Unsafe run identifier")
    print(name)
PY
failed=0
while IFS= read -r id; do
  echo "=== Uploading existing run: $id ==="
  if ! bash scripts/publish_results.sh "$ROOT/runs/$id"; then
    echo "WARNING: Could not publish $id; no VM rerun is needed" >&2
    failed=$((failed+1))
  fi
done < "$names"
if ((failed)); then
  echo "$failed upload(s) failed. Retry when SSH is available." >&2
  exit 1
fi
echo "All completed runs in the selected batch are uploaded."
