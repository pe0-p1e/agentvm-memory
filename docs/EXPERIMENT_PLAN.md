# Experimental plan

**RQ1:** After guest anonymous pages are released, how much of the host Firecracker process remains resident?

**RQ2:** How much does explicit virtio-balloon inflation recover, and how quickly does its `actual_mib` converge to `target_mib`?

**RQ3:** Does free-page reporting reclaim pages without setting a nonzero balloon target?

All use 1 vCPU, 1024 MiB nominal RAM, 512 MiB touched anonymous pages, Ubuntu x86_64 kernel from Firecracker demo, same rootfs, same workload (12s idle, 22s allocated, 90s after free). Record host RSS and balloon stats at ~1 Hz. Store exact git sha, kernel/rootfs hashes and Firecracker version.

Primary outcomes: host RSS median per stage (MiB), RSS delta from allocated→freed and freed→reclaim; time series of `actual_mib` vs `target_mib`. Guardrails: guest `oom_kill`, `major_faults`, incomplete balloon convergence or guest boot failure. Treat invalid/missing samples as missing, not zero. Use paired comparisons only across the same binary/kernel and close time windows. Do not interpret host VmSize as physical memory use.

Next experiments after baseline: 3–5 repeated trials, randomized mode order, 256/512/768 MiB memory targets, memory-pressure workload, time-to-reclaim, and guest page fault overhead. AgentENV integration should be a separate adapter after confirming cluster ownership and API entrypoint with the lab; do not manipulate the already-running AgentENV processes on cpu-15.
