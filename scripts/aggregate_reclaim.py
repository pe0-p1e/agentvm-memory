#!/usr/bin/env python3
"""Aggregate a single sequential Firecracker experiment batch (no external deps)."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

METRICS = {
    "rss_reclaimed_mib": ("memory", "rss_reclaimed_mib"),
    "pss_reclaimed_mib": ("memory", "pss_reclaimed_mib"),
    "free_to_80pct_s": ("memory", "free_observation_to_80pct_reclaim_s"),
    "inflate_to_80pct_s": ("balloon_api", "inflate_request_to_80pct_reclaim_s"),
    "inflate_api_ms": ("balloon_api", "inflate_api_wall_ms"),
    "deflate_api_ms": ("balloon_api", "deflate_api_wall_ms"),
    "code_latency_ratio": ("agent_tool_replay", "after_reclaim_vs_before_latency_ratio"),
    "memory_touch_ratio": ("memory_touch", "second_vs_first_touch_latency_ratio"),
}

def summarize(batch_dir):
    batch_dir = Path(batch_dir).resolve()
    entries = [json.loads(line) for line in (batch_dir / "manifest.jsonl").read_text().splitlines() if line.strip()]
    if not entries:
        raise ValueError("empty experiment batch")
    runs_root = batch_dir.parent.parent
    records = []
    commits = set()
    used = set()
    for entry in entries:
        rid = entry["run_id"]
        if not rid.startswith("20") or "/" in rid or "\\" in rid or rid in used:
            raise ValueError("invalid or duplicate run ID")
        used.add(rid)
        path = runs_root / rid
        report = json.loads((path / "reclaim.json").read_text())
        metadata = json.loads((path / "metadata.json").read_text())
        validation = json.loads((path / "validation.json").read_text())
        if not validation["valid"] or not report["valid"]:
            raise ValueError("invalid run: " + rid)
        if entry["mode"] != report["mode"] or entry["mode"] != metadata["mode"]:
            raise ValueError("mode mismatch: " + rid)
        if metadata.get("workload") != "deterministic_code_repair_tool_replay":
            raise ValueError("unexpected workload: " + rid)
        commit = metadata["source_commit"]
        commits.add(commit)
        values = {}
        for name, keys in METRICS.items():
            item = report
            for key in keys:
                item = item.get(key) if isinstance(item, dict) else None
            values[name] = item
        records.append({"trial": entry["trial"], "mode": entry["mode"], "run_id": rid, "metrics": values})
    if len(commits) != 1:
        raise ValueError("mixed source commits cannot be pooled")
    grouped = defaultdict(list)
    for r in records:
        grouped[r["mode"]].append(r["metrics"])
    stats = {}
    for mode, group in sorted(grouped.items()):
        stats[mode] = {"n": len(group), "metrics": {}}
        for name in METRICS:
            nums = [float(x[name]) for x in group if x[name] is not None]
            stats[mode]["metrics"][name] = ({
                "n": len(nums), "median": round(median(nums), 4),
                "min": round(min(nums), 4), "max": round(max(nums), 4)
            } if nums else None)
    return {
        "batch_id": batch_dir.name,
        "source_commit": next(iter(commits)),
        "runs": records,
        "by_mode": stats,
        "caveats": [
            "These are repeated VM runs; six episodes within one run are not six independent VMs.",
            "Min/max over few runs are descriptive, not confidence intervals.",
            "One shared server, deterministic tool replay; this is not live AgentENV or an LLM agent.",
            "The free-to-reclaim latency includes intentional policy delay and serial polling.",
        ],
    }

def write(batch_dir):
    batch = Path(batch_dir)
    result = summarize(batch)
    (batch / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("Batch:", result["batch_id"], "Source:", result["source_commit"][:12])
    print(f'{"mode":<11} {"n":>3} {"RSS MiB":>12} {"PSS MiB":>12} {"touch ratio":>13} {"code ratio":>12}')
    for mode, value in result["by_mode"].items():
        metrics = value["metrics"]
        def fmt(name):
            x = metrics[name]
            return f'{x["median"]:.3f}' if x else "NA"
        print(f'{mode:<11} {value["n"]:>3} {fmt("rss_reclaimed_mib"):>12} {fmt("pss_reclaimed_mib"):>12} {fmt("memory_touch_ratio"):>13} {fmt("code_latency_ratio"):>12}')
    print("Wrote:", batch / "aggregate.json")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_dir")
    args = ap.parse_args()
    write(args.batch_dir)

if __name__ == "__main__":
    main()
