#!/usr/bin/env python3
"""Host-only Firecracker RSS / virtio-balloon sampling."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import time

FIELDS = [
    'timestamp_utc', 'elapsed_s', 'phase', 'host_rss_mib', 'host_rssanon_mib',
    'host_rssfile_mib', 'balloon_target_mib', 'balloon_actual_mib',
    'guest_available_mib', 'guest_free_mib', 'guest_total_mib',
    'guest_major_faults', 'guest_minor_faults', 'guest_oom_kills',
    'guest_direct_reclaim', 'sample_ok',
]


def read_proc_status(pid):
    result = {}
    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key in {'VmRSS', 'RssAnon', 'RssFile'}:
            result[key] = int(value.strip().split()[0]) / 1024
    return result


def read_balloon(socket):
    cmd = ['curl', '--fail', '--silent', '--show-error', '--max-time', '3',
           '--unix-socket', socket, 'http://localhost/balloon/statistics']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or 'balloon request failed')
    return json.loads(proc.stdout)


def sample(pid, socket, phase, start):
    rss = read_proc_status(pid)
    b = read_balloon(socket)
    def mb(name):
        return round(b[name] / 1048576, 3) if b.get(name) is not None else ''
    return {
        'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'elapsed_s': round(time.monotonic()-start, 3),
        'phase': phase,
        'host_rss_mib': rss.get('VmRSS', ''),
        'host_rssanon_mib': rss.get('RssAnon', ''),
        'host_rssfile_mib': rss.get('RssFile', ''),
        'balloon_target_mib': b.get('target_mib', ''),
        'balloon_actual_mib': b.get('actual_mib', ''),
        'guest_available_mib': mb('available_memory'),
        'guest_free_mib': mb('free_memory'),
        'guest_total_mib': mb('total_memory'),
        'guest_major_faults': b.get('major_faults', ''),
        'guest_minor_faults': b.get('minor_faults', ''),
        'guest_oom_kills': b.get('oom_kill', ''),
        'guest_direct_reclaim': b.get('direct_reclaim', ''),
        'sample_ok': 1,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', required=True, type=int)
    ap.add_argument('--socket', required=True)
    ap.add_argument('--phase', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--stop-file', required=True)
    args = ap.parse_args()
    start = time.monotonic()
    errors_path = Path(args.output).with_suffix('.errors.log')
    with open(args.output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        while not Path(args.stop_file).exists():
            try:
                phase = Path(args.phase).read_text().strip()
                record = sample(args.pid, args.socket, phase, start)
                writer.writerow(record)
                f.flush()
            except (FileNotFoundError, ProcessLookupError):
                break
            except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as ex:
                with errors_path.open('a') as err:
                    err.write(f'{time.time()}: {type(ex).__name__} {ex}\n')
            time.sleep(1)


if __name__ == '__main__':
    main()
