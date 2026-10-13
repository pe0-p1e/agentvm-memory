# Phase 2: AgentENV memory lifecycle experiments

## Why this is necessary

The initial raw Firecracker results (2026-10-13) demonstrate that balloon inflation and free-page reporting reduce host RSS. They do **not** test AgentENV's memory-reclamation policy, idle/reuse lifecycle, snapshot interactions, recovery latency, multi-sandbox consolidation, or real agent workloads.

The next question is not whether ballooning works. It is **when and how AgentENV invokes its memory policy and what the throughput/latency consequences are.**

## Experimental stages

1. **Read-only discovery, no sandbox creation.** Run `python3 scripts/agentenv_preflight.py` on the host. This probes only the user-owned AENV CLI and its read-only list commands, reports counts/status without names/IDs/tokens, and writes `runs/agentenv-preflight-*/preflight.json`. Do not publish server/private metadata to the public repo without review.
2. **Single disposable sandbox, authorized template.** After verifying your own API credentials and an approved template, create exactly one new sandbox using `aenv start <template> --detach --timeout 900`. Record its ID only locally, and never operate on IDs belonging to other users.
3. **Same guest memory workload.** Guest allocates/touches 512 MiB anonymous memory, holds, releases, then idles. Measure host RSS/PSS **only if the newly created sandbox can be reliably mapped to its exact VMM PID**, plus guest MemAvailable, success/failure, and time-to-reclaim. If VM-PID attribution is ambiguous, mark it unavailable rather than using host-wide memory as a surrogate.
4. **Pause/resume and reuse.** From the same disposable sandbox, measure elapsed pause and resume times, host RSS before/after, and first command latency after resume. Only pause the sandbox created by this experiment.
5. **Repeated trials.** At least five runs for baseline and reclamation controls, three workload types (anonymous alloc/free, Python/process exit, compilation/file I/O), with p50/p95 cold-start/resume and recovered MiB. Log host load, KSM setting, guest kernel, CPU/NUMA placement. Repeat isolated, not simultaneous, before multi-sandbox contention studies.

## First-wave raw Firecracker references

- Baseline: `results/20261013T075228Z-baseline-1398545`
- Balloon: `results/20261013T075446Z-balloon-1399991`
- Free-page reporting: `results/20261013T075701Z-reporting-1401442`

For the same 512 MiB allocation, host RSS after guest free remained ~633.98 MiB in baseline; balloon 0 -> 512 -> 0 resulted in ~125.41 MiB host RSS; free-page reporting resulted in ~181.22 MiB. These are *one trial per condition*, not independent repeated statistics.

## Current lab constraints

- Use only your own host user account and authorized AgentENV API access.
- AgentENV is already operated by other lab users on cpu-15. Do **not** reinstall, restart or stop that service, modify global network/KSM settings, or kill other Firecracker/ublk processes.
- Never retrieve another user's API key via sudo/Docker exec. Request an appropriately scoped key or permission from the instance owner.
- Do not use `aenv delete`, `pause`, `resume`, `exec`, or `snapshot` with any sandbox ID that was not created by your experiment.
- Do not automatically publish credentials, sandbox identifiers, internal endpoints or service logs to this repo (currently Public).
- The CLI may be missing even if the server is running; a missing CLI does not imply the server is absent.

## User-scoped AENV CLI bootstrap (no server changes)

On `cpu-15` as your unprivileged user, while Mihomo is running:

```bash
source ~/.config/mihomo/proxy.env
cd ~/agentvm-memory
git -c http.version=HTTP/1.1 fetch \
  https://github.com/pe0-p1e/agentvm-memory.git \
  '+refs/heads/exp/agentenv-memory:refs/remotes/origin/exp/agentenv-memory'
git switch exp/agentenv-memory
git merge --ff-only origin/exp/agentenv-memory
bash scripts/bootstrap_agentenv_cli.sh
export PATH="$HOME/.local/bin:$PATH"
aenv --help
```

The bootstrap explicitly checks `jq`, `curl`, `tar`, `gzip`, and `sha256sum` before running the official CLI-only installer; missing tools trigger a safe failure rather than an unplanned `sudo apt-get`.

An installed CLI **does not imply API authorization**. Ask the AgentENV instance owner for an endpoint and an API key that you are explicitly allowed to use; never copy a lab-global server secret from Docker or root-only locations. Then run:

```bash
aenv auth
python3 scripts/agentenv_preflight.py
```

Do not paste the API key or full `aenv list` output into public messages.

## Preflight

```bash
cd ~/agentvm-memory
git fetch origin
git switch --track origin/exp/agentenv-memory  # or: git switch exp/agentenv-memory
python3 scripts/agentenv_preflight.py
```

If the CLI is missing, use the official user-scoped `install-cli.sh` *only with lab approval*, not the server install script and not a privileged Docker reinstall.

Upstream documentation: https://kvcache-ai.github.io/AgentENV/latest/getting-started/aenv-cli.html and https://github.com/kvcache-ai/AgentENV
