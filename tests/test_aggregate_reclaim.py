#!/usr/bin/env python3
"""Unit tests for batch aggregation without a Firecracker/KVM host."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("aggregate_reclaim", ROOT/"scripts/aggregate_reclaim.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AggregateTests(unittest.TestCase):
    def create_run(self, root, trial, mode, commit="abc123", reclaimed=0):
        name = "20261014T120000Z-" + mode + "-" + str(trial)
        p = root / name
        p.mkdir()
        report = {
            "valid": True, "mode": mode,
            "memory": {"rss_reclaimed_mib": reclaimed, "pss_reclaimed_mib": reclaimed},
            "balloon_api": {},
            "agent_tool_replay": {"after_reclaim_vs_before_latency_ratio": 1.01},
            "memory_touch": {"second_vs_first_touch_latency_ratio": 0.85}
        }
        (p/"reclaim.json").write_text(json.dumps(report))
        (p/"validation.json").write_text(json.dumps({"valid": True}))
        (p/"metadata.json").write_text(json.dumps({
            "mode": mode, "source_commit": commit,
            "workload": "deterministic_code_repair_tool_replay"
        }))
        return {"trial": trial, "mode": mode, "run_id": name}

    def test_batch_statistics_and_provenance(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            batch = root / "batches" / "batch-1"
            batch.mkdir(parents=True)
            entries = [
                self.create_run(root, 1, "baseline", reclaimed=0.0),
                self.create_run(root, 1, "balloon", reclaimed=500.0),
                self.create_run(root, 2, "balloon", reclaimed=510.0)
            ]
            (batch/"manifest.jsonl").write_text(
                "".join(json.dumps(entry) + "\n" for entry in entries))
            result = module.summarize(batch)
            self.assertEqual(result["by_mode"]["balloon"]["n"], 2)
            self.assertEqual(result["by_mode"]["balloon"]["metrics"]["rss_reclaimed_mib"]["median"], 505)
            self.assertEqual(result["source_commit"], "abc123")

    def test_mixed_source_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            batch = root / "batches" / "batch-2"
            batch.mkdir(parents=True)
            entries = [
                self.create_run(root, 1, "baseline", commit="abc123"),
                self.create_run(root, 1, "balloon", commit="def789")
            ]
            (batch/"manifest.jsonl").write_text(
                "".join(json.dumps(entry) + "\n" for entry in entries))
            with self.assertRaisesRegex(ValueError, "mixed source commits"):
                module.summarize(batch)

if __name__ == "__main__":
    unittest.main()
