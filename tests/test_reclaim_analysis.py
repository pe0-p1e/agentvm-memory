#!/usr/bin/env python3
"""Host-only unit tests: tool replay and reclaim analysis without Firecracker."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

analysis=load("analysis","scripts/analyze_reclaim.py")
agent=load("agent","guest/agent_replay.py")

class ReclaimTests(unittest.TestCase):
    def test_real_tool_invocations(self):
        x=agent.run("smoke",3)
        self.assertTrue(x["success"])
        self.assertEqual(x["episodes"],3)
        self.assertFalse(x["llm_inference"])
        self.assertEqual(len(x["latency_ms"]),3)

    def test_synthetic_parser(self):
        rows=[]
        for phase,rss,pss,ts in [
            ("allocated",634,628,10),("allocated",634,628,11),
            ("freed",634,628,12),("freed",632,626,13),
            ("balloon_deflated",125,120,14),("balloon_deflated",125,120,15),
            ("retouched",634,628,17),("retouched",634,628,18)]:
            rows.append({"sample_ok":"1","phase":phase,"host_rss_mib":str(rss),
                         "host_pss_mib":str(pss),"epoch_s":str(ts),
                         "host_cpu_s":str(ts/10)})
        phases=["before_allocation","after_reclaim","after_retouch"]
        console="\n".join("FCMEM_AGENT_JSON:"+json.dumps({
            "label":k,"success":True,"episodes":6,"llm_inference":False,
            "latency_median_ms":100+i*2}) for i,k in enumerate(phases))
        console+="\n"+"\n".join("FCMEM_RETOUCH_JSON:"+json.dumps({
            "label":k,"latency_ms":30+i*10})
            for i,k in enumerate(["first_touch","second_touch"]))
        events=[{"event":"guest_marker_seen","detail":"freed","epoch_s":12},
                {"event":"balloon_inflate_before","detail":"512","epoch_s":13},
                {"event":"balloon_inflate_after","detail":"512","epoch_s":13.04}]
        r=analysis.analyze(rows,console,events,
                           {"mode":"balloon","balloon_mib":512},{"valid":True})
        self.assertTrue(r["valid"])
        self.assertEqual(r["memory"]["rss_reclaimed_mib"],509)
        self.assertTrue(r["memory"]["reached_80pct_of_512mib"])
        self.assertAlmostEqual(r["balloon_api"]["inflate_api_wall_ms"],40)
        self.assertFalse(r["is_real_llm_agent"])

    def test_reject_missing_guest_results(self):
        with self.assertRaises(ValueError):
            analysis.analyze([], "", [],
                             {"mode":"baseline","balloon_mib":512},{"valid":True})

if __name__=="__main__":
    unittest.main()
