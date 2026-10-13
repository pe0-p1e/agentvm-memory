#!/usr/bin/env python3
"""Timestamp host-side experiment events (no sensitive data)."""
import json
from pathlib import Path
import sys
import time
if len(sys.argv) < 3:
    raise SystemExit("Usage: host_events.py JSONL EVENT [DETAIL]")
record = {"event": sys.argv[2], "detail": sys.argv[3] if len(sys.argv)>3 else "",
          "epoch_s": time.time(), "monotonic_s": time.monotonic()}
with Path(sys.argv[1]).open("a") as file:
    file.write(json.dumps(record, sort_keys=True) + "\n")
