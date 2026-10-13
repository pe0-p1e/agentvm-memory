#!/usr/bin/env python3
"""Read-only AgentENV environment probe; never prints API credentials or VM IDs."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"

def call(args, timeout=15):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired):
        return None, "", ""

def shape_count(raw):
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for k in ("data", "items", "templates", "sandboxes"):
            v = data.get(k)
            if isinstance(v, list):
                return len(v)
    return None

def main():
    if os.geteuid() == 0:
        sys.exit("Run as the normal host user, not root.")
    if platform.node() == "ubuntu-fc-uvm":
        sys.exit("You are inside a Firecracker guest; run on cpu-15 host.")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = RUNS / ("agentenv-preflight-" + stamp)
    path.mkdir(parents=True, exist_ok=False)
    choices = [shutil.which("aenv"), str(Path.home() / ".local/bin/aenv"),
               "/usr/local/bin/aenv", "/usr/bin/aenv"]
    binary = next((x for x in choices if x and Path(x).is_file() and os.access(x, os.X_OK)), None)
    config_present = (Path.home() / ".config/aenv/credentials").is_file()
    report = {
        "purpose": "read_only_agentenv_preflight",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_kernel": platform.release(),
        "aenv_cli_available": bool(binary),
        "aenv_credentials_file_present": config_present,
        "template_list_status": "not_attempted",
        "sandbox_list_status": "not_attempted",
    }
    if binary:
        code, stdout, _ = call([binary, "--version"], timeout=5)
        report["aenv_cli_version"] = stdout.strip()[:150] if code == 0 else "unavailable"
        # These commands are read-only, and their raw output (names, IDs, paths)
        # is never stored or printed.
        for label, args in [
            ("template", [binary, "template", "list", "--output", "json"]),
            ("sandbox", [binary, "list", "--output", "json"]),
        ]:
            code, stdout, _ = call(args)
            report[f"{label}_list_status"] = ("ok" if code == 0 else
                                               "error" if code is not None else "timeout_or_unavailable")
            if code == 0:
                report[f"{label}_count"] = shape_count(stdout)
    output = path / "preflight.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"\nRead-only report: {output}")
    print("No sandboxes, templates, containers, or services were created or modified.")
    if not binary:
        print("AENV CLI missing. Install user-scoped CLI only with lab approval.")
    elif not config_present:
        print("AENV CLI found, but no user-owned credentials were found; request lab-approved access.")
    elif report["template_list_status"] != "ok":
        print("AENV read-only API access failed; check your own credentials and endpoint.")
    else:
        print("Read-only preflight complete. Select an authorized disposable template for stage 2.")
if __name__ == "__main__":
    main()
