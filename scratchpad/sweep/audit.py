#!/usr/bin/env python3
"""Best local-scoring file for <slug> across ALL worktrees + submitted archives."""
import glob, json, subprocess, sys, os, hashlib
R="/Users/visenbaev/icfpc26"
slug=sys.argv[1]
roots=[R]+glob.glob(R+"/.claude/worktrees/*")
pats=[]
for root in roots:
    pats += [f"{root}/solutions/{slug}/**/*.man", f"{root}/submitted/{slug}/**/*.man",
             f"{root}/submitted/{slug}.man", f"{root}/scratchpad/**/{slug}*.man"]
seen=set(); best=[]
for pat in pats:
    for f in glob.glob(pat, recursive=True):
        try: h=hashlib.md5(open(f,'rb').read()).hexdigest()
        except Exception: continue
        if h in seen: continue
        seen.add(h)
        try:
            d=json.loads(subprocess.run([sys.executable,f"{R}/tools/grade_fast.py",slug,f],
                capture_output=True,text=True,timeout=200).stdout.strip())
        except Exception: continue
        if d.get("passed")==d.get("total") and d.get("score"):
            best.append((d["score"], d["footprint"]["box"], f))
best.sort()
print("SLUG %s files=%d passing=%d" % (slug, len(seen), len(best)), flush=True)
for s,b,f in best[:3]:
    print("   %14.0f box %-6d %s" % (s,b,f.replace(R+"/","")), flush=True)
