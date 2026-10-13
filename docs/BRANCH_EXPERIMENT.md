# exp/free-page-reporting

Same guest anonymous-memory workload as `main`, with preboot `free_page_reporting=true` and balloon target zero throughout. Measures whether the guest's reported unused memory pages reduce host Firecracker RSS without manual balloon inflation. Requires guest kernel `CONFIG_PAGE_REPORTING`; if the RSS does not decrease, validate the guest kernel before interpreting a negative result.
