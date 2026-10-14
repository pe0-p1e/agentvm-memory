#!/usr/bin/env python3
"""Guest phases for host-memory reclamation costs and actual tool-use replay."""
import gc
import json
import mmap
import subprocess
import sys
import time

sys.path.insert(0, "/opt/fc-memory")
from agent_replay import run

SIZE = 512 * 1024 * 1024
STEP = 4096

def serial(line):
    with open("/dev/ttyS0", "ab", buffering=0) as f:
        f.write((line + "\n").encode("ascii", "replace"))

def mark(stage):
    serial("FCMEM_STAGE:" + stage)

def emit(key, data):
    serial("FCMEM_" + key + "_JSON:" + json.dumps(data, sort_keys=True))

def touch(mm):
    begin = time.perf_counter()
    for offset in range(0, SIZE, STEP):
        mm[offset] = 1
    return round((time.perf_counter()-begin)*1000, 3)

def allocate():
    return mmap.mmap(-1, SIZE, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                     prot=mmap.PROT_READ | mmap.PROT_WRITE)

def main():
    try:
        mark("baseline")
        time.sleep(3)
        emit("AGENT", run("before_allocation"))
        time.sleep(8)
        mm = allocate()
        first_ms = touch(mm)
        emit("RETOUCH", {"label": "first_touch", "mib": 512, "latency_ms": first_ms})
        mark("allocated")
        time.sleep(22)
        mm.close()
        del mm
        gc.collect()
        mark("freed")
        # The host runner uses this idle window to inflate/deflate balloon or
        # wait for free-page reporting; 66 s > host's 12+20+20s control period.
        time.sleep(66)
        mark("agent_reuse")
        time.sleep(2.5)  # Host can now sample the replay phase
        emit("AGENT", run("after_reclaim"))
        mark("retouch_start")
        time.sleep(2.5)  # Host can now sample the pre-touch phase
        mm2 = allocate()
        second_ms = touch(mm2)
        emit("RETOUCH", {"label": "second_touch", "mib": 512,
                         "latency_ms": second_ms})
        mark("retouched")
        time.sleep(2.5)  # Host can now sample the post-touch phase
        emit("AGENT", run("after_retouch"))
        time.sleep(8)
        mm2.close()
        mark("done")
    except BaseException as exc:
        serial("FCMEM_STAGE:error:{}:{}".format(type(exc).__name__, str(exc)))
        raise

if __name__ == "__main__":
    main()
