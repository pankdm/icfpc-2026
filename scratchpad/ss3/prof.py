#!/usr/bin/env python3
"""subset-sum profiler WITH --input (the thing that was missing on plotter)."""
import json, re, subprocess, sys, os
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
from grade_fast import rounds_of
from collections import defaultdict
MAN=sys.argv[1]; CASE=sys.argv[2]; CAP=sys.argv[3] if len(sys.argv)>3 else "15000000"
spec=json.load(open("/Users/visenbaev/icfpc26/tests/subset-sum.json"))
case=[t for t in spec["publicTestData"] if t["name"]==CASE][0]
inp,exp,frames=rounds_of(case)
cmd=["/Users/visenbaev/icfpc26/interp/target/release/lm","--profile",MAN,
     "--input="+inp,"--expected="+exp,"--cap="+CAP]
if frames: cmd.append("--frames="+frames)
r=subprocess.run(cmd,capture_output=True,text=True)
print("stdout:", r.stdout.strip()[:200])
err=r.stderr
PAIR=re.compile(r"\(\((-?\d+), (-?\d+)\), (\d+)\)")
def sec(n):
    m=re.search(r"PROFILE %s=(\[.*?\])\n"%n,err,re.S); return m.group(1) if m else ""
cells=[(int(x),int(y),int(n)) for x,y,n in PAIR.findall(sec("cells"))]
stalls={(int(x),int(y)):int(n) for x,y,n in PAIR.findall(sec("stalls"))}
grid=open(MAN).read().split("\n")
tot=sum(c[2] for c in cells); tots=sum(stalls.values())
print("exec=%d stall=%d cells=%d"%(tot,tots,len(cells)))
rows=defaultdict(lambda:[0,0,0])
for x,y,n in cells:
    rows[y][0]+=n; rows[y][1]+=stalls.get((x,y),0); rows[y][2]+=1
top=sorted(rows.items(), key=lambda kv:-kv[1][0])[:14]
print("hottest rows: exec stall ncells")
for y,(e,s,c) in top:
    print("  row %3d %9d %9d %4d | %s"%(y,e,s,c,(grid[y] if y<len(grid) else "")[:70]))
cells.sort(key=lambda t:-t[2])
print("hottest cells:")
for x,y,n in cells[:12]:
    ch=grid[y][x] if y<len(grid) and x<len(grid[y]) else "?"
    print("  (%3d,%3d) '%s' exec=%9d stall=%9d"%(x,y,ch,n,stalls.get((x,y),0)))
