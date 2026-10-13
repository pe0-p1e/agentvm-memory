#!/usr/bin/env python3
"""Measure reclaimed memory, approximate reclamation latency and tool replay cost."""
import csv
import json
from pathlib import Path
import statistics
import sys

def median(rows, phase, field):
    values=[]
    for row in rows:
        if row.get("sample_ok")=="1" and row.get("phase")==phase:
            value=row.get(field)
            if value not in ("",None):
                try: values.append(float(value))
                except ValueError: pass
    return round(statistics.median(values),3) if values else None

def parse_console(text,prefix):
    result={}
    for line in text.splitlines():
        if prefix not in line: continue
        item=json.loads(line.split(prefix,1)[1].strip().split('\r')[0])
        if item["label"] in result: raise ValueError("Duplicate "+prefix+item["label"])
        result[item["label"]]=item
    return result

def timestamp(events,event,detail=None):
    found=[float(row["epoch_s"]) for row in events if row["event"]==event and
           (detail is None or row.get("detail")==detail)]
    return found[0] if found else None

def cpu_phase(rows,phase):
    points=[]
    for row in rows:
        if row.get("sample_ok")!="1" or row.get("phase")!=phase: continue
        if row.get("host_cpu_s") in ("",None) or row.get("epoch_s") in ("",None):continue
        points.append((float(row["epoch_s"]),float(row["host_cpu_s"])))
    if len(points)<2:return None
    dt=points[-1][0]-points[0][0]
    cpu=points[-1][1]-points[0][1]
    return {"host_cpu_s":round(cpu,3),"elapsed_s":round(dt,3),
            "cpu_seconds_per_second":round(cpu/dt,3) if dt>0 else None}

def phase_faults(rows,phase):
    result={}
    for field in ("host_minor_faults","host_major_faults",
                  "guest_minor_faults","guest_major_faults"):
        values=[]
        for row in rows:
            if row.get("sample_ok")=="1" and row.get("phase")==phase:
                val=row.get(field)
                if val not in ("",None):
                    try: values.append(float(val))
                    except ValueError: pass
        result[field+"_delta"]=int(max(0,values[-1]-values[0])) if len(values)>=2 else None
    return result

def analyze(rows,console,events,meta,validation):
    mode=meta["mode"]
    after_phase={"baseline":"control_after_free",
                 "balloon":"balloon_deflated",
                 "reporting":"reporting_after_free"}[mode]
    if not validation.get("valid"):raise ValueError("Prior run invalid")
    agent=parse_console(console,"FCMEM_AGENT_JSON:")
    touch=parse_console(console,"FCMEM_RETOUCH_JSON:")
    need={"before_allocation","after_reclaim","after_retouch"}
    if not need.issubset(agent) or not {"first_touch","second_touch"}.issubset(touch):
        raise ValueError("Guest replay or touch event missing")
    if any(not agent[k].get("success") or agent[k].get("episodes")!=6 or
           agent[k].get("llm_inference") is not False for k in need):
        raise ValueError("Guest replay failed or invalid LLM label")
    allocated=median(rows,"allocated","host_rss_mib")
    post=median(rows,after_phase,"host_rss_mib")
    pss_a=median(rows,"allocated","host_pss_mib")
    pss_b=median(rows,after_phase,"host_pss_mib")
    if allocated is None or post is None:raise ValueError("Host RSS samples missing")
    free_seen=timestamp(events,"guest_marker_seen","freed")
    target=allocated-0.8*float(meta["balloon_mib"])
    first=None
    if free_seen is not None:
        for r in rows:
            if r.get("sample_ok")!="1":continue
            try:
                if float(r["epoch_s"])>=free_seen and float(r["host_rss_mib"])<=target:
                    first=float(r["epoch_s"]);break
            except (ValueError,KeyError,TypeError):pass
    delays={}
    for kind in ("inflate","deflate"):
        a=timestamp(events,"balloon_"+kind+"_before")
        b=timestamp(events,"balloon_"+kind+"_after")
        delays[kind+"_api_wall_ms"]=round(1000*(b-a),3) if a is not None and b is not None else None
    base=agent["before_allocation"]["latency_median_ms"]
    next_time=agent["after_reclaim"]["latency_median_ms"]
    first_ms=touch["first_touch"]["latency_ms"]
    second_ms=touch["second_touch"]["latency_ms"]
    return {
        "valid":True,"mode":mode,"source_commit":meta.get("source_commit"),
        "workload_type":"deterministic_code_repair_tool_replay","is_real_llm_agent":False,
        "sampling_interval_s":meta.get("monitor_interval_s"),
        "memory":{
            "rss_allocated_mib":allocated,"rss_after_reclaim_mib":post,
            "rss_reclaimed_mib":round(allocated-post,3),
            "rss_after_retouch_mib":median(rows,"retouched","host_rss_mib"),
            "pss_allocated_mib":pss_a,"pss_after_reclaim_mib":pss_b,
            "pss_reclaimed_mib":round(pss_a-pss_b,3) if pss_a is not None and pss_b is not None else None,
            "reached_80pct_of_512mib":first is not None,
            "free_observation_to_80pct_reclaim_s":
                round(max(0,first-free_seen),3) if first is not None else None
        },
        "balloon_api":delays,
        "agent_tool_replay":{
            "phases":agent,
            "after_reclaim_vs_before_latency_ratio":round(next_time/base,4) if base>0 else None
        },
        "memory_touch":{
            "phases":touch,
            "second_vs_first_touch_latency_ratio":round(second_ms/first_ms,4) if first_ms>0 else None
        },
        "host_cpu_by_phase":{p:cpu_phase(rows,p) for p in
            ("allocated","freed","control_after_free","balloon_inflated",
             "balloon_deflated","reporting_after_free","agent_reuse","retouch","retouched")},
        "faults_by_phase":{p:phase_faults(rows,p) for p in
            ("allocated","freed","control_after_free","balloon_inflated",
             "balloon_deflated","reporting_after_free","agent_reuse","retouch","retouched")},
        "limitations":[
            "One trial per condition unless the suite is repeated.",
            "The 80% reclamation delay includes the intentional host policy delay.",
            "The console marker is polled once per second, and host metrics twice per second.",
            "Tool replay is real subprocess/file I/O but uses deterministic planning, not a live LLM agent.",
            "Free-page reporting needs Guest kernel capability verification."
        ]
    }

def main():
    if len(sys.argv)!=2:raise SystemExit("Usage: analyze_reclaim.py RUN_DIR")
    root=Path(sys.argv[1])
    with (root/"metrics.csv").open(newline="") as file:rows=list(csv.DictReader(file))
    events=[json.loads(line) for line in (root/"host-events.jsonl").read_text().splitlines() if line.strip()]
    report=analyze(rows,(root/"guest-console.log").read_text(errors="replace"),events,
                   json.loads((root/"metadata.json").read_text()),
                   json.loads((root/"validation.json").read_text()))
    (root/"reclaim.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("Reclamation:",report["mode"])
    print("Host RSS reclaimed (MiB):",report["memory"]["rss_reclaimed_mib"])
    print("Host PSS reclaimed (MiB):",report["memory"]["pss_reclaimed_mib"])
    print("Code-tool replay slowdown:",report["agent_tool_replay"]["after_reclaim_vs_before_latency_ratio"])
    print("Memory touch slowdown:",report["memory_touch"]["second_vs_first_touch_latency_ratio"])
    print("Not a live LLM-Agent benchmark.")

if __name__=="__main__":main()
