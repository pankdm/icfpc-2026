#!/usr/bin/env python3
import json, re, subprocess, sys
MAN=sys.argv[1]; CASE=sys.argv[2]; CAP=sys.argv[3]
N=int(sys.argv[4]) if len(sys.argv)>4 else 25
spec=json.load(open("tests/plotter.json"))
case=[t for t in spec["publicTestData"] if t["name"]==CASE][0]
open("/tmp/pf.json","w").write(json.dumps(case["rounds"]))
r=subprocess.run(["interp/target/release/lm","--profile",MAN,"--frames-file=/tmp/pf.json","--cap="+CAP],capture_output=True,text=True)
err=r.stderr
PAIR=re.compile(r"\(\((-?\d+), (-?\d+)\), (\d+)\)")
def sec(n):
    m=re.search(r"PROFILE %s=(\[.*?\])\n"%n,err,re.S); return m.group(1) if m else ""
cells=[(int(x),int(y),int(n)) for x,y,n in PAIR.findall(sec("cells"))]
stalls={(int(x),int(y)):int(n) for x,y,n in PAIR.findall(sec("stalls"))}
grid=open(MAN).read().split("\n")
cells.sort(key=lambda t:-t[2])
print("stdout:", r.stdout.strip()[:120])
for x,y,n in cells[:N]:
    ch=grid[y][x] if y<len(grid) and x<len(grid[y]) else '?'
    print("(%2d,%2d) '%s' exec=%4d stall=%4d"%(x,y,ch,n,stalls.get((x,y),0)))
print("ncells", len(cells), "sum", sum(c[2] for c in cells))
