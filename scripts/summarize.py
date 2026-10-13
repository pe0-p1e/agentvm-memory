#!/usr/bin/env python3
"""Summarize valid samples by experiment phase; no synthetic data."""
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PHASES = ['baseline', 'allocated', 'freed', 'balloon_inflated', 'balloon_deflated', 'reporting_after_free', 'control_after_free', 'agent_reuse', 'retouch', 'retouched']
METRICS = ['host_rss_mib', 'host_rssanon_mib', 'balloon_actual_mib', 'guest_available_mib', 'guest_major_faults', 'host_pss_mib', 'host_cpu_s']


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        if row.get('sample_ok') == '1':
            grouped[row['phase']].append(row)
    result = {}
    for phase in PHASES:
        samples = grouped[phase]
        if not samples:
            continue
        m = {'samples': len(samples)}
        for key in METRICS:
            values = [float(s[key]) for s in samples if s.get(key) not in ('', None)]
            m[key + '_median'] = round(statistics.median(values), 3) if values else None
        result[phase] = m
    return result


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python3 scripts/summarize.py metrics.csv summary.json')
    with open(sys.argv[1], newline='') as f:
        data = summarize(csv.DictReader(f))
    Path(sys.argv[2]).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    print(f"{'phase':<22} {'N':>5} {'host RSS MiB':>16} {'balloon MiB':>14} {'guest avail MiB':>18}")
    for phase, row in data.items():
        def fmt(key):
            v = row[key]
            return f'{v:.1f}' if v is not None else 'NA'
        print(f"{phase:<22} {row['samples']:>5} {fmt('host_rss_mib_median'):>16} {fmt('balloon_actual_mib_median'):>14} {fmt('guest_available_mib_median'):>18}")


if __name__ == '__main__':
    main()
