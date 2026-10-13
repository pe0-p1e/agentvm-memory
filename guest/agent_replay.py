#!/usr/bin/env python3
"""Offline tool-use coding workload replay.

Executes real Python test processes, filesystem inspection, code edits, and
regression tests. The *plan* is deterministic: this is NOT an LLM agent.
Runs wholly inside a disposable Firecracker guest without network credentials.
"""
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import tempfile
import time

TASKS = [
    {
        "module": "def average(values):\n    return sum(values) // len(values)\n",
        "test": "import unittest\nfrom task import average\nclass T(unittest.TestCase):\n"
                "    def test_fraction(self):\n        self.assertEqual(average([1,2]), 1.5)\n"
                "    def test_integer(self):\n        self.assertEqual(average([2,4]), 3)\n",
        "before": "sum(values) // len(values)",
        "after": "sum(values) / len(values)",
    },
    {
        "module": "def normalize(text):\n    return text.strip().lower().replace('  ', ' ')\n",
        "test": "import unittest\nfrom task import normalize\nclass T(unittest.TestCase):\n"
                "    def test_whitespace(self):\n        self.assertEqual(normalize(' A   B '), 'a b')\n"
                "    def test_case(self):\n        self.assertEqual(normalize(' Ab '), 'ab')\n",
        "before": "text.strip().lower().replace('  ', ' ')",
        "after": "' '.join(text.lower().split())",
    },
    {
        "module": "def is_even(n):\n    return n % 2 == 1\n",
        "test": "import unittest\nfrom task import is_even\nclass T(unittest.TestCase):\n"
                "    def test_even(self):\n        self.assertTrue(is_even(12))\n"
                "    def test_odd(self):\n        self.assertFalse(is_even(7))\n",
        "before": "n % 2 == 1",
        "after": "n % 2 == 0",
    },
]

def command(argv, cwd):
    p = subprocess.run(argv, cwd=str(cwd), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=25, check=False)
    if p.returncode not in (0, 1):
        raise RuntimeError("tool command failed (exit code {})".format(p.returncode))
    return p.returncode

def episode(task, work):
    module = work / "task.py"
    module.write_text(task["module"])
    (work / "test_task.py").write_text(task["test"])
    # Tool 1: inspect working directory. Tool 2: test and observe failure.
    filenames = sorted(p.name for p in work.iterdir())
    if "task.py" not in filenames or "test_task.py" not in filenames:
        raise AssertionError("project inspection failed")
    before = command([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"], work)
    if before != 1:
        raise AssertionError("expected failing regression before repair")
    # Tool 3: read and apply a deterministic repair. No model inference.
    code = module.read_text()
    if code.count(task["before"]) != 1:
        raise AssertionError("repair precondition failed")
    module.write_text(code.replace(task["before"], task["after"]))
    # Tool 4: compile and run the regression suite.
    if command([sys.executable, "-m", "py_compile", str(module)], work) != 0:
        raise AssertionError("compile failed")
    after = command([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"], work)
    if after != 0:
        raise AssertionError("regression still failing")

def run(label, repeats=6):
    elapsed = []
    before_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    for i in range(repeats):
        start = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="fc-code-repair-") as tmp:
            episode(TASKS[i % len(TASKS)], Path(tmp))
        elapsed.append((time.perf_counter()-start)*1000)
    after_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {
        "label": label,
        "workload": "deterministic_code_repair_tool_replay",
        "llm_inference": False,
        "episodes": repeats,
        "success": True,
        "latency_ms": [round(x, 3) for x in elapsed],
        "latency_median_ms": round(statistics.median(elapsed), 3),
        "latency_max_ms": round(max(elapsed), 3),
        "child_cpu_s": round((after_usage.ru_utime - before_usage.ru_utime)
                             + (after_usage.ru_stime - before_usage.ru_stime), 4),
        "child_major_faults": after_usage.ru_majflt - before_usage.ru_majflt,
        "child_minor_faults": after_usage.ru_minflt - before_usage.ru_minflt,
    }
    return result

if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else "smoke"),
                     sort_keys=True))
