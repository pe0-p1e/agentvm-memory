#!/usr/bin/env python3
"""Conservative measurement sanity checks; do not invent or silently fill missing samples."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

REQUIRED_PHASES = {
    'baseline': ['baseline', 'allocated', 'freed', 'control_after_free'],
    'balloon': ['baseline', 'allocated', 'freed', 'balloon_inflated', 'balloon_deflated'],
    'reporting': ['baseline', 'allocated', 'freed', 'reporting_after_free'],
}


def validate(mode, rows, console):
    if mode not in REQUIRED_PHASES:
        raise ValueError('Unknown mode')
    phases = Counter(r['phase'] for r in rows if r.get('sample_ok') == '1')
    missing = [p for p in REQUIRED_PHASES[mode] if phases[p] < 2]
    markers = ['baseline', 'allocated', 'freed', 'agent_reuse',
               'retouch_start', 'retouched', 'done']
    missing_markers = [m for m in markers if 'FCMEM_STAGE:' + m not in console]
    warnings = []
    if mode == 'balloon':
        inflated = [r for r in rows if r.get('phase') == 'balloon_inflated'
                    and r.get('sample_ok') == '1' and r.get('balloon_actual_mib')]
        if not inflated:
            warnings.append('No balloon actual_mib measurements in balloon_inflated phase')
        elif max(float(r['balloon_actual_mib']) for r in inflated) < 1:
            warnings.append('Balloon actual_mib never increased: verify guest virtio-balloon driver')
    if mode == 'reporting' and 'Free page reporting enabled' not in console:
        warnings.append('Guest did not log Free page reporting enabled: check PAGE_REPORTING')
    return {'mode': mode, 'valid': not (missing or missing_markers),
            'samples_by_phase': dict(phases),
            'missing_phases': missing, 'missing_guest_markers': missing_markers,
            'warnings': warnings}


def main():
    if len(sys.argv) != 5:
        raise SystemExit('Usage: validate_run.py MODE metrics.csv guest-console.log validation.json')
    mode, csv_path, console_path, out = sys.argv[1:]
    with open(csv_path, newline='') as f:
        rows = list(csv.DictReader(f))
    report = validate(mode, rows, Path(console_path).read_text(errors='replace'))
    Path(out).write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('VALIDATION:', 'PASS' if report['valid'] else 'FAIL', report['warnings'])
    if not report['valid']:
        raise SystemExit('Incomplete experiment. Check validation.json and logs before publishing.')


if __name__ == '__main__':
    main()
