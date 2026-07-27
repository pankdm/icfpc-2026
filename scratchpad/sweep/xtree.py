#!/usr/bin/env python3
"""Grade every .man for <slug> across ALL worktrees; report anything beating <best>."""
import glob, json, subprocess, sys, os, hashlib
R="/Users/visenbaev/icfpc26"
slug=sys.argv[1]; thresh=float(sys.argv[2])
roots=[R]+glob.glob(R+"/.claude/worktrees/*")
seen=set(); out=[]
for root in roots:
    for f in glob.glob(f"{root}/solutions/{slug}/**/*.man", recursive=True)+ \
             glob.glob(f"{root}/submitted/{slug}/**/*.man", recursive=True)+ \
             glob.glob(f"{root}/submitted/{slug}.man"):
        try: h=hashlib.md5(open(f,'rb').read()).hexdigest()
        except Exception: continue
        if h in seen: continue
        seen.add(h)
        try:
            d=json.loads(subprocess.run([sys.executable,f"{R}/tools/grade_fast.py",slug,f],
                capture_output=True,text=True,timeout=240).stdout.strip())
        except Exception: continue
        if d.get("passed")==d.get("total") and d.get("score") and d["score"]<thresh:
            out.append((d["score"],f)); print("BETTER %.0f %s"%(d["score"],f),flush=True)
print("done",slug,"candidates",len(seen),"better",len(out),flush=True)
