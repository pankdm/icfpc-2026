#!/usr/bin/env python3
"""Correct plotter profiler: passes --input/--expected/--frames like grade_fast.
usage: prof.py <man> <case> [rows|cells] [N]"""
import json, re, subprocess, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from grade_fast import rounds_of
from collections import defaultdict
MAN=sys.argv[1]; CASE=sys.argv[2]
MODE=sys.argv[3] if len(sys.argv)>3 else "rows"
N=int(sys.argv[4]) if len(sys.argv)>4 else 25
spec=json.load(open("tests/plotter.json"))
case=[t for t in spec["publicTestData"] if t["name"]==CASE][0]
inp,exp,frames=rounds_of(case)
cmd=["interp/target/release/lm","--profile",MAN,"--input="+inp,"--expected="+exp,"--cap=5000000"]
if frames: cmd.append("--frames="+frames)
r=subprocess.run(cmd,capture_output=True,text=True)
err=r.stderr
print("stdout:",r.stdout.strip()[:150])
PAIR=re.compile(r"\(\((-?\d+), (-?\d+)\), (\d+)\)")
def sec(n):
    m=re.search(r"PROFILE %s=(\[.*?\])\n"%n,err,re.S); return m.group(1) if m else ""
cells=[(int(x),int(y),int(n)) for x,y,n in PAIR.findall(sec("cells"))]
stalls={(int(x),int(y)):int(n) for x,y,n in PAIR.findall(sec("stalls"))}
grid=open(MAN).read().split("\n")
tot=sum(c[2] for c in cells); tots=sum(stalls.values())
print("exec=%d stall=%d"%(tot,tots))
if MODE=="rows":
    rows=defaultdict(lambda:[0,0,0])
    for x,y,n in cells:
        rows[y][0]+=n; rows[y][1]+=stalls.get((x,y),0); rows[y][2]+=1
    print("row  exec  stall  ncells | line")
    for y in sorted(rows):
        e,s,c=rows[y]; line=grid[y] if y<len(grid) else ""
        print("%3d %6d %6d %4d | %s"%(y,e,s,c,line[:54]))
else:
    cells.sort(key=lambda t:-t[2])
    for x,y,n in cells[:N]:
        ch=grid[y][x] if y<len(grid) and x<len(grid[y]) else '?'
        print("(%2d,%2d) '%s' exec=%4d stall=%4d"%(x,y,ch,n,stalls.get((x,y),0)))
