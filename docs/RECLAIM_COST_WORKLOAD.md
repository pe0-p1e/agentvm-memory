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
The guest deliberately holds each reuse phase for 2.5 seconds so Host samples
can be attributed to the correct phase rather than racing the workload.

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

For the full 5-trial design, keep execution independent of unstable GitHub SSH:

~~~bash
bash scripts/run_reclaim_suite.sh --repeats 5 |& tee ~/reclaim-v2-repeat5.log
~~~

The suite records completed runs in a new `runs/batches/<batch_id>/manifest.jsonl`
and writes `aggregate.json` after every successful VM run. If a GitHub push
fails, completed runs remain on disk and **must not be rerun simply to retry
publishing**.

When the proxy is stable and logs have been checked for secrets, publish the
latest batch without running any VMs:

~~~bash
bash scripts/publish_batch.sh
~~~

To publish a specific batch, pass its path to `publish_batch.sh`.
A transient SSH failure is retried up to four times for the same result
commit (`PUBLISH_RETRIES=1..6`). Publishing may still fail; retry later.
`--publish` is also supported during the experiment suite, but an upload
failure now prints a warning and **does not terminate the next VM trial**.

If an older run was completed under a previous code version, publish it
separately with `bash scripts/publish_results.sh runs/<run_id>`, and do
not merge that historical run into the current batch's statistical summary.

The script removes only the **newly copied disposable rootfs** after
successful runs (to save space), leaving metrics and logs intact.

## Measurements

- metrics.csv: Host VMM RSS/PSS, VMM CPU seconds, Host VMM faults,
  balloon target/actual stats, Guest memory and Guest faults, 0.5s polls
- host-events.jsonl: 1-second-polled markers from Guest serial, plus
  balloon API boundary timestamps
- runs/batches/<batch_id>/manifest.jsonl: all completed run identifiers
- runs/batches/<batch_id>/aggregate.json: run-level median/min/max for
  independently repeated VMs, verifying a single source commit.
  The suite rotates experiment mode order across trials to reduce order bias.
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
- The host runner deliberately delays balloon inflation by 12 s. The
  free-to-reclaim metric includes that policy wait, but
  balloon_api.inflate_request_to_80pct_reclaim_s isolates the request-to-RSS
  threshold interval (still limited by 0.5-second sampling).
- Agent tool-run latency and memory-touch latency are separate outcomes. The
  median across six tool episodes is a within-run statistic, not six independent
  VM repetitions.
- Guest console marker detection uses 1-second polling; Host RSS sampling
  is at 2 Hz, so sub-second/microsecond latency cannot be concluded.
- Guest support for free-page reporting is checked against the boot line
  "Free page reporting enabled"; absence produces a validation warning.
  Mechanism attribution remains limited without Guest-side tracepoints.
- Repeated trials are sequential but may still be affected by shared-server
  background noise; use >=3 to 5 and report variability.
- The GitHub repository is PUBLIC. Never publish API keys, personal data,
  agent prompts, unrelated server output, or other users' VM identifiers.

## Version 2 design

For every run, the same experimental source commit records the complete
Firecracker setup, Guest replay and host metrics. The 5-repetition suite gives
15 independently created Firecracker VM runs in rotating condition order.
The aggregate report includes median and observed range. These are not
statistical confidence intervals, and the shared server still introduces noise.

Two time bases must not be conflated:
- **guest-free observation -> 80% recovery**: overall policy + mechanism.
- **balloon inflate request -> 80% recovery**: post-trigger approximation.

A new series must not be pooled with the October 13 pilot, which used a
different source commit and shorter guest stage boundaries. If a run fails,
its incomplete logs stay local and the batch manifest contains only completed
runs. The lab AgentENV service is never restarted or touched by this suite.
