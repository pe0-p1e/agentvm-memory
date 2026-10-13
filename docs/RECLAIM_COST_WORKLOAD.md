# Firecracker reclaim cost and coding-tool workload

This is a **real Firecracker host/guest experiment** but it is NOT an AgentENV
benchmark and NOT a live LLM-Agent benchmark. The guest executes real
subprocess and filesystem operations for a deterministic coding-repair
workflow: list files -> observe test failures -> edit source -> compile ->
rerun tests until passing.

The three configurations run from **one Git branch** in sequence:
- baseline (no active balloon, no free-page reporting)
- virtio balloon inflates 0 -> 512 -> 0 MiB
- free-page reporting enabled, balloon always at 0 MiB.

Each configuration tests 512 MiB anonymous-memory allocation, free, 66 s idle,
then tool replay, a second 512 MiB page touch, and tool replay again.

## Running on cpu-15

Run on the host only. The lab's live AgentENV service is not touched.

~~~bash
source ~/.config/mihomo/proxy.env
cd ~/agentvm-memory
git -c http.version=HTTP/1.1 fetch \
  https://github.com/pe0-p1e/agentvm-memory.git \
  '+refs/heads/exp/reclaim-cost-workload:refs/remotes/origin/exp/reclaim-cost-workload'
git switch --track origin/exp/reclaim-cost-workload \
  || git switch exp/reclaim-cost-workload
git merge --ff-only origin/exp/reclaim-cost-workload

python3 -m unittest discover -s tests -v
bash -n scripts/*.sh
bash scripts/run_reclaim_suite.sh --repeats 1
~~~

Then inspect generated files in runs, and publish only after confirming they
contain no server secrets or private workloads:

~~~bash
for f in runs/*/reclaim.json; do
  echo "==== $f ===="
  python3 -m json.tool "$f" | head -80
done
~~~

If logs are safe to disclose, publish successful runs with the existing
script, or rerun a series directly with:

~~~bash
bash scripts/run_reclaim_suite.sh --publish --repeats 3
~~~

The script removes only the **newly copied disposable rootfs** after
successful runs (to save space), leaving metrics and logs intact.

## Measurements

- metrics.csv: Host VMM RSS/PSS, VMM CPU seconds, Host VMM faults,
  balloon target/actual stats, Guest memory and Guest faults, 0.5s polls
- host-events.jsonl: 1-second-polled markers from Guest serial, plus
  balloon API boundary timestamps
- guest-console.log: actual executed workload results and memory touches
- reclaim.json: RSS/PSS reclaimed, time-to-threshold bound, Host CPU by phase,
  balloon API request wall time, tool-replay performance ratio, and
  512 MiB second-touch slowdown
- validation.json / summary.json / metadata.json: quality and provenance

Important caveats:
- This is a **deterministic offline tool workload**, not an actual LLM planner,
  nor does it exercise the authenticated AgentENV control plane. To obtain
  real agent workload data, access an authorized AgentENV instance and run an
  actual coding agent or recorded production Agent trace in a new sandbox.
- The current host runner deliberately delays balloon inflation by 12 s;
  free-to-reclaim delay includes that policy wait.
- Guest console marker detection uses 1-second polling; Host RSS sampling
  is at 2 Hz, so sub-second/microsecond latency cannot be concluded.
- Free-page reporting Guest kernel support has not been independently verified.
- Repeated trials are sequential but may still be affected by shared-server
  background noise; use >=3 to 5 and report variability.
- The GitHub repository is PUBLIC. Never publish API keys, personal data,
  agent prompts, unrelated server output, or other users' VM identifiers.
