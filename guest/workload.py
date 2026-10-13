#!/usr/bin/env python3
"""Run inside a Firecracker guest. Stage markers travel over ttyS0 to the host."""
import gc
import mmap
import os
import subprocess
import time

MARKER = 'FCMEM_STAGE'


def mark(stage):
    msg = f'{MARKER}:{stage}\n'.encode('ascii')
    with open('/dev/ttyS0', 'ab', buffering=0) as serial:
        serial.write(msg)
    print(msg.decode().strip(), flush=True)
    subprocess.run(['/usr/bin/free', '-m'], check=False)


def main():
    try:
        mark('baseline')
        time.sleep(12)
        amount = 512 * 1024 * 1024
        mm = mmap.mmap(-1, amount, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                       prot=mmap.PROT_READ | mmap.PROT_WRITE)
        for off in range(0, amount, 4096):
            mm[off] = 1
        mark('allocated')
        time.sleep(22)
        mm.close()
        gc.collect()
        mark('freed')
        time.sleep(90)  # permit host-side balloon and comparison windows
        mark('done')
    except BaseException as exc:
        try:
            with open('/dev/ttyS0', 'ab', buffering=0) as serial:
                serial.write(f'{MARKER}:error:{type(exc).__name__}:{exc}\n'.encode('ascii', 'replace'))
        finally:
            raise


if __name__ == '__main__':
    main()
