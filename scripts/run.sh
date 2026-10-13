#!/usr/bin/env bash
# Firecracker allocation/free/balloon experiment. Run on the cpu-15 HOST.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"  # Always record the experiment repository commit, not caller cwd.
CFG="${1:-$ROOT/configs/default.env}"
[[ -f "$CFG" ]] || { echo "Config missing: $CFG" >&2; exit 2; }
# shellcheck source=/dev/null
source "$CFG"
MODE="${MODE:-baseline}"
MEMORY_MIB="${MEMORY_MIB:-1024}"
BALLOON_MIB="${BALLOON_MIB:-512}"
FREE_PAGE_REPORTING="${FREE_PAGE_REPORTING:-false}"
[[ "$MODE" =~ ^(baseline|balloon|reporting)$ ]] || { echo "Invalid mode $MODE" >&2; exit 2; }
[[ "$MEMORY_MIB" =~ ^[0-9]+$ && "$BALLOON_MIB" =~ ^[0-9]+$ ]] || exit 2
((MEMORY_MIB >= 896 && BALLOON_MIB < MEMORY_MIB - 192)) || { echo 'Unsafe memory settings' >&2; exit 2; }
[[ "$FREE_PAGE_REPORTING" == true || "$FREE_PAGE_REPORTING" == false ]] || exit 2
[[ "$(hostname)" != ubuntu-fc-uvm ]] || { echo 'ERROR: You are inside guest; use host cpu-15' >&2; exit 2; }
(( EUID != 0 )) || { echo 'ERROR: use normal host login, not root' >&2; exit 2; }
for cmd in curl python3 mountpoint git sha256sum find mktemp ps sudo; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 2; }
done
[[ -r /dev/kvm && -w /dev/kvm ]] || { echo '/dev/kvm access denied' >&2; exit 2; }

FC_BASE="${FC_BASE:-$HOME/sandbox-study/firecracker}"
FC="${FC_BINARY:-$FC_BASE/build/cargo_target/$(uname -m)-unknown-linux-musl/debug/firecracker}"
DEMO="${FC_DEMO:-$FC_BASE/demo}"
KERNEL="${FC_KERNEL:-$(find "$DEMO" -maxdepth 1 -type f -name 'vmlinux-*' | sort -V | tail -1)}"
ROOTFS="${FC_ROOTFS:-$(find "$DEMO" -maxdepth 1 -type f -name '*.ext4' | sort -V | head -1)}"
[[ -x "$FC" && -f "$KERNEL" && -f "$ROOTFS" ]] || {
  echo "Missing Firecracker/kernel/rootfs: FC=$FC KERNEL=$KERNEL ROOTFS=$ROOTFS" >&2; exit 2;
}
FC="$(realpath "$FC")"; KERNEL="$(realpath "$KERNEL")"; ROOTFS="$(realpath "$ROOTFS")"
# Refuse to copy the previous demo image while its Firecracker is still serving requests.
OLD_SOCKET="/tmp/firecracker-${USER}.socket"
if [[ -S "$OLD_SOCKET" ]] && curl -fsS --max-time 2 --unix-socket "$OLD_SOCKET" http://localhost/machine-config >/dev/null 2>&1; then
  echo 'Please power off your old interactive demo VM before running this experiment.' >&2
  exit 2
fi
[[ $(df -Pk "$ROOT" | awk 'NR==2 {print $4}') -ge 2097152 ]] || {
  echo 'Less than 2 GiB disk free; refusing to run on shared server.' >&2; exit 2;
}

mkdir -p "$ROOT/runs"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${MODE}-$$"
RUN_DIR="$ROOT/runs/$RUN_ID"
mkdir -p "$RUN_DIR"
DISK="$RUN_DIR/guest.ext4"
MOUNT_DIR="$RUN_DIR/mnt"
CONSOLE="$RUN_DIR/guest-console.log"
VMM_LOG="$RUN_DIR/firecracker.log"
PHASE="$RUN_DIR/phase"
CSV="$RUN_DIR/metrics.csv"
STOP_FILE="$RUN_DIR/stop-monitor"
SOCK="/tmp/fcmem-$(id -u)-$$.sock"
FC_PID=""; MON_PID=""; MOUNTED=0

say() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
cleanup() {
  status=$?
  trap - EXIT INT TERM
  touch "$STOP_FILE"
  if [[ -n "$MON_PID" ]]; then kill "$MON_PID" 2>/dev/null || true; wait "$MON_PID" 2>/dev/null || true; fi
  if [[ -n "$FC_PID" ]]; then kill "$FC_PID" 2>/dev/null || true; wait "$FC_PID" 2>/dev/null || true; fi
  if [[ "$MOUNTED" == 1 ]]; then sudo umount "$MOUNT_DIR" || true; fi
  rm -f -- "$SOCK"
  if [[ -d "$RUN_DIR" ]]; then
    printf '\nResults: %s\n' "$RUN_DIR"
    printf 'metrics: %s\nsummary: %s\nconsole: %s\n' "$CSV" "$RUN_DIR/summary.json" "$CONSOLE"
    if (( status != 0 )); then printf 'Run exited with status %d; inspect logs.\n' "$status" >&2; fi
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

say "Mode: $MODE; run: $RUN_ID"
say 'Copying rootfs, not modifying the original'
cp --sparse=always --reflink=auto "$ROOTFS" "$DISK"
mkdir -p "$MOUNT_DIR"
# Mount only an isolated copy of the rootfs; no persistent host changes.
sudo mount -o loop "$DISK" "$MOUNT_DIR"
MOUNTED=1
[[ -e "$MOUNT_DIR/usr/bin/python3" ]] || { echo 'Guest rootfs has no /usr/bin/python3' >&2; exit 3; }
sudo install -D -m 0644 "$ROOT/guest/workload.py" "$MOUNT_DIR/opt/fc-memory/workload.py"
sudo install -D -m 0644 "$ROOT/guest/agent_replay.py" "$MOUNT_DIR/opt/fc-memory/agent_replay.py"
sudo install -D -m 0644 "$ROOT/guest/fc-memory.service" "$MOUNT_DIR/etc/systemd/system/fc-memory.service"
sudo mkdir -p "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants"
sudo ln -sfn ../fc-memory.service "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants/fc-memory.service"
sudo umount "$MOUNT_DIR"
MOUNTED=0

# Guest serial output is its own file; VMM diagnostics go elsewhere.
: > "$CONSOLE"; : > "$VMM_LOG"
"$FC" --api-sock "$SOCK" > "$CONSOLE" 2> "$VMM_LOG" < /dev/null &
FC_PID=$!
for _ in $(seq 1 100); do
  [[ -S "$SOCK" ]] && break
  kill -0 "$FC_PID" 2>/dev/null || { echo 'VMM exited on startup' >&2; exit 3; }
  sleep .1
done
[[ -S "$SOCK" ]] || { echo 'No API socket' >&2; exit 3; }

api() {
  local method="$1" endpoint="$2" payload="${3:-}"
  if [[ -n "$payload" ]]; then
    curl -fsS --max-time 10 --unix-socket "$SOCK" -X "$method" \
      -H 'Content-Type: application/json' --data "$payload" "http://localhost$endpoint"
  else
    curl -fsS --max-time 10 --unix-socket "$SOCK" -X "$method" "http://localhost$endpoint"
  fi
}
json_boot="$(python3 -c 'import json,sys;print(json.dumps({"kernel_image_path":sys.argv[1],"boot_args":"console=ttyS0 reboot=k panic=1 pci=off"}))' "$KERNEL")"
json_disk="$(python3 -c 'import json,sys;print(json.dumps({"drive_id":"rootfs","path_on_host":sys.argv[1],"is_root_device":True,"is_read_only":False}))' "$DISK")"
api PUT /machine-config "{\"vcpu_count\":1,\"mem_size_mib\":$MEMORY_MIB}"
api PUT /boot-source "$json_boot"
api PUT /drives/rootfs "$json_disk"
api PUT /balloon "{\"amount_mib\":0,\"deflate_on_oom\":false,\"stats_polling_interval_s\":1,\"free_page_reporting\":$FREE_PAGE_REPORTING,\"free_page_hinting\":false}"
# stdout is already redirected; serial is captured there by default.
# We intentionally do not configure /serial: this works on pre-serial-API builds too.

python3 - "$RUN_DIR" "$MODE" "$FC" "$KERNEL" "$ROOTFS" "$MEMORY_MIB" "$BALLOON_MIB" "$FREE_PAGE_REPORTING" <<'PY'
import hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
out,mode,fc,kernel,rootfs,mem,balloon,report = sys.argv[1:]
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            b=f.read(1024*1024)
            if not b: break
            h.update(b)
    return h.hexdigest()
def cmd(args):
    try: return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return None
meta={'mode':mode,'memory_mib':int(mem),'balloon_mib':int(balloon),'free_page_reporting':report=='true',
      'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'host_kernel':platform.release(),'host_machine':platform.machine(),
      'firecracker_binary':fc,'firecracker_version':cmd([fc,'--version']),
      'guest_kernel_sha256':digest(kernel),'source_rootfs_sha256':digest(rootfs),
      'source_commit':cmd(['git','rev-parse','HEAD']), 'workload':'deterministic_code_repair_tool_replay', 'monitor_interval_s':0.5}
Path(out,'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
PY

event() { python3 "$ROOT/scripts/host_events.py" "$RUN_DIR/host-events.jsonl" "$1" "${2:-}"; }
set_phase() { echo "$1" > "$PHASE"; event phase "$1"; say "Phase: $1"; }
wait_marker() {
  local marker="$1" limit="$2" i
  for ((i=0;i<limit;i++)); do
    if grep -aFq "FCMEM_STAGE:$marker" "$CONSOLE"; then event guest_marker_seen "$marker"; return 0; fi
    if grep -aFq 'FCMEM_STAGE:error:' "$CONSOLE"; then echo 'Guest workload error' >&2; return 1; fi
    if ! kill -0 "$FC_PID" 2>/dev/null; then echo 'VMM exited early' >&2; return 1; fi
    sleep 1
  done
  echo "Timed out waiting for guest marker $marker. Inspect $CONSOLE" >&2
  return 1
}
set_phase booting
python3 "$ROOT/scripts/monitor.py" --pid "$FC_PID" --socket "$SOCK" \
    --phase "$PHASE" --output "$CSV" --stop-file "$STOP_FILE" --interval 0.5 &
MON_PID=$!
say 'Booting guest'
api PUT /actions '{"action_type":"InstanceStart"}'
wait_marker baseline 150
set_phase baseline
wait_marker allocated 80
set_phase allocated
wait_marker freed 80
set_phase freed
sleep 12
case "$MODE" in
  balloon)
    say "Inflating balloon to $BALLOON_MIB MiB"
    event balloon_inflate_before "$BALLOON_MIB"
    api PATCH /balloon "{\"amount_mib\":$BALLOON_MIB}"
    event balloon_inflate_after "$BALLOON_MIB"
    set_phase balloon_inflated
    sleep 20
    say 'Deflating balloon to zero'
    event balloon_deflate_before "0"
    api PATCH /balloon '{"amount_mib":0}'
    event balloon_deflate_after "0"
    set_phase balloon_deflated
    sleep 20
    ;;
  reporting)
    set_phase reporting_after_free
    sleep 40
    ;;
  baseline)
    set_phase control_after_free
    sleep 40
    ;;
esac
wait_marker agent_reuse 120
set_phase agent_reuse
wait_marker retouch_start 120
set_phase retouch
wait_marker retouched 120
set_phase retouched
wait_marker done 120
say 'Workload done; stopping the experiment process'
touch "$STOP_FILE"
wait "$MON_PID" || true
MON_PID=""
python3 "$ROOT/scripts/summarize.py" "$CSV" "$RUN_DIR/summary.json"
python3 "$ROOT/scripts/validate_run.py" "$MODE" "$CSV" "$CONSOLE" "$RUN_DIR/validation.json"
python3 "$ROOT/scripts/analyze_reclaim.py" "$RUN_DIR"
say 'Completed successfully. Run scripts/publish_results.sh if desired.'
