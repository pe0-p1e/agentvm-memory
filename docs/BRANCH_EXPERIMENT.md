# exp/balloon

The same guest anonymous-memory workload as `main`, but after guest release the host inflates virtio-balloon from 0 → 512 MiB, waits 20 seconds, then deflates to zero. This records `target_mib`, `actual_mib`, host RSS and guest available memory in each stage. `free_page_reporting=false` for isolation of this mechanism.
