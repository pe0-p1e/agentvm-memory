# Firecracker Agent Memory Lab

Reproducible host/guest experiments for **anonymous memory allocation, guest free, host RSS, virtio-balloon reclaim**, and virtio **free-page reporting**. Intended for an isolated microVM on the `cpu-15` laboratory host, **not** for modifying the pre-existing AgentENV service.

**中文一页式操作说明：** [`docs/QUICKSTART_ZH.md`](docs/QUICKSTART_ZH.md)

## Experiments / branches

| Git branch | Preboot reporting | Host balloon after guest `free` | Control question |
|---|---|---|---|
| `main` | off | none | Does guest `free` lower host RSS on its own? |
| `exp/balloon` | off | 0 → 512 → 0 MiB | Can explicit inflation reclaim host RSS? |
| `exp/free-page-reporting` | on | none | Will guest-driven free-page reporting reclaim host RSS? |

All branches run the **same** guest workload: 1 vCPU, 1 GiB guest, 512 MiB anonymous mapping, touch each 4 KiB page, hold, then `mmap.close()`. The three source branches intentionally differ only in `configs/default.env` and a short branch note. Re-run all branches with `./scripts/run_all.sh`. Each run uses a unique socket and a **copy** of the guest ext4 image.

## Source repository and CPU-15 bootstrap

**GitHub:** <https://github.com/pe0-p1e/agentvm-memory>. Source experiment branches are maintained here. The GitHub repository is currently **public**; review logs carefully before publishing results and consider changing visibility to Private if the lab prefers it.

On the **cpu-15 host** (`fyzhou@cpu-15`, not the microVM guest):

```bash
git clone https://github.com/pe0-p1e/agentvm-memory.git ~/agentvm-memory
cd ~/agentvm-memory
python3 -m unittest discover -s tests -v
```

**Recommended on networks blocking GitHub SSH 22 and 443: authenticated HTTPS.** The results uploader supports both HTTPS and SSH origins on all three experiment branches. For HTTPS:

```bash
git remote set-url origin https://github.com/pe0-p1e/agentvm-memory.git
git config --local credential.helper 'cache --timeout=7200'
git fetch origin
git ls-remote origin HEAD
./scripts/run_all.sh --publish
```

For the first authenticated HTTPS push, Git prompts for username `pe0-p1e` and password: paste a **fine-grained personal access token** with repository access limited to `agentvm-memory` and **Contents: Read and write**. Create it at <https://github.com/settings/personal-access-tokens/new>. Do not put tokens in remote URLs, Git config, scripts, or shell commands. The `cache` helper retains the credential in memory temporarily instead of writing plaintext to disk; omit it if you prefer a prompt on every push.

Alternative, when SSH is reachable: `./scripts/setup_ssh.sh`, register the public key in this repo's Deploy keys with write access, and use `git@github.com:pe0-p1e/agentvm-memory.git` as origin. Outbound SSH is **not required** for these experiments.

`--publish` creates a separate `results/<run-id>` branch for each successful run; it does **not** overwrite experiment branches. The repository is public: review logs before publishing results.

## Run (on cpu-15 only)

Assumes you previously built Firecracker v1.18.0-dev locally and created the Ubuntu `.ext4` image and `vmlinux-*` in `~/sandbox-study/firecracker/demo`. Stop your earlier interactive Firecracker demo before copying the rootfs. Do **not** stop any AgentENV Firecracker processes.

```bash
cd ~/agentvm-memory
./scripts/run.sh                     # on main: untreated baseline
./scripts/run_all.sh                 # baseline, balloon, reporting on separate branches
./scripts/run_all.sh --publish       # also push each completed run to its own results/<run-id> branch
```

A single experiment can be selected explicitly, without switching branches:

```bash
./scripts/run.sh configs/balloon.env
```

Optional environment overrides: `FC_BASE`, `FC_DEMO`, `FC_BINARY`, `FC_KERNEL`, `FC_ROOTFS`; paths may be absolute. No Docker builds, TAP network setup, host KSM changes, or AgentENV service changes are performed.

**Prerequisites:** Linux x86_64, working `/dev/kvm`, Firecracker binary, writable guest ext4 rootfs, `sudo mount/umount` of *copied* disk, host `curl`, `python3`, `find`, `git` and at least ~2 GiB free disk. The guest image must have `systemd`, `/usr/bin/python3`, `/dev/ttyS0`, and functional virtio-balloon driver. If free-page reporting has no effect, verify `CONFIG_PAGE_REPORTING` in guest kernel and `page_reporting` status. Existing rootfs files are not patched in place.

## Evidence and interpretation

Each run creates `runs/<UTC timestamp>-<mode>-<pid>/` (ignored by Git):

- `metadata.json` — host kernel, Firecracker binary version, source git SHA, kernel/rootfs SHA256, scenario.
- `metrics.csv` — 1 Hz host process RSS / RssAnon / RssFile and guest balloon statistics. Sampling starts **on host** before VM boot.
- `summary.json` — phase-level medians; no synthetic data.
- `validation.json` — evidence of stage coverage and warnings; incomplete runs are rejected.
- `guest-console.log` — guest stage events (`FCMEM_STAGE:baseline`, `allocated`, `freed`, `done`).
- `firecracker.log` — VMM stderr for troubleshooting.
- `guest.ext4` — disposable copy of guest image, never published.

A completed run can be uploaded separately via `./scripts/publish_results.sh runs/<run-id>`; **only logs/CSV/metadata/summary/validation** are pushed, not ext4 images, SSH keys or host credentials. Each upload creates a new `results/<run-id>` branch derived from the source branch used for that run; it does not edit `main`.

Host RSS may **not** decline after guest free; balloon `target_mib=512` does **not** guarantee actual pages reached 512. Deflation does **not** imply those host pages are immediately faulted back. Guest total is typically slightly less than the configured 1024 MiB. These are measurements, not assumed outcomes.

**Experimental limitations:** this is a first-stage functional baseline, not a production performance benchmark. CPU NUMA placement, KSM (enabled on this host), guest allocator specifics, page-cache effects, and shared-host interference may affect RSS. To compare the scenarios scientifically, run repeated trials and record host load/NUMA state. `guest_available_mib` is reported by the balloon driver and may be absent/stale if guest balloon stats are unavailable. Free-page reporting relies on the guest kernel supporting that feature.

## Safe scope

Never run `pkill firecracker`, stop Docker/AgentENV services, prune caches or modify global KSM settings. The runner starts exactly one Firecracker process and cleans up **only its own child process**. It copies the guest rootfs, mounts only that copy temporarily, and unmounts it even on error. The single-node shared host is not safe for uncontrolled memory pressure; keep settings at or below the default until cleared by the lab.

## Testing

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/*.sh
```
