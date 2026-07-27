#!/usr/bin/env python3
"""Grade every .man in solutions/<slug>/ and report the lowest-scoring passer."""
import glob, json, subprocess, sys, os
R="/Users/visenbaev/icfpc26"
slug=sys.argv[1]
files=sorted(glob.glob(f"{R}/solutions/{slug}/**/*.man", recursive=True))
best=None
for f in files:
    try:
        out=subprocess.run([sys.executable,f"{R}/tools/grade_fast.py",slug,f],
                           capture_output=True,text=True,timeout=240).stdout.strip()
        d=json.loads(out)
    except Exception:
        continue
    if d.get("passed")==d.get("total") and d.get("score"):
        if best is None or d["score"]<best[1]:
            best=(f,d["score"],d["footprint"]["box"])
    print("  %-52s %s/%s %s"%(os.path.basename(f),d.get("passed"),d.get("total"),d.get("score")),flush=True)
print("BEST",slug,best,flush=True)
