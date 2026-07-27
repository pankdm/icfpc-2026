#!/usr/bin/env python3
"""Sweep swar_build's routing knobs; keep only builds that pass 6/6."""
import itertools, json, os, subprocess, sys
HERE="/Users/visenbaev/icfpc26"
B=os.path.join(HERE,"solutions/plotter/swar_build.py")
G=os.path.join(HERE,"tools/grade_fast.py")
best=[]
combos=list(itertools.product([2,3],[1,2],[0,1,2],range(0,13),[2,3,4]))
for gap,swap,swcol,zig,atoff in combos:
    out="/tmp/sw_%d_%d_%d_%d_%d.man"%(gap,swap,swcol,zig,atoff)
    r=subprocess.run([sys.executable,B,"--gap",str(gap),"--swap-rows",str(swap),
                      "--swcol",str(swcol),"--zig",str(zig),"--atoff",str(atoff),
                      "--out",out,"--quiet"],capture_output=True,text=True,cwd=os.path.dirname(B))
    if r.returncode!=0: continue
    g=subprocess.run([sys.executable,G,"plotter",out],capture_output=True,text=True,cwd=HERE)
    try: d=json.loads(g.stdout)
    except Exception: continue
    if d.get("passed")!=6: continue
    best.append((d["score"],d["footprint"]["box"],round(d["avgTicks"],1),gap,swap,swcol,zig,atoff))
best.sort()
for b in best[:12]:
    print("score=%10.0f box=%4d ticks=%7.1f gap=%d swap=%d swcol=%d zig=%2d atoff=%d"%b)
print("passing:",len(best),"of",len(combos))
