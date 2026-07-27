#!/usr/bin/env python3
"""Per-region exec ticks (exec includes stall).  usage: regions.py <man> <case> <cap>"""
import json, re, subprocess, sys
from collections import defaultdict
MAN = sys.argv[1]; CASE = sys.argv[2]; CAP = sys.argv[3]
spec = json.load(open("tests/plotter.json"))
case = [t for t in spec["publicTestData"] if t["name"] == CASE][0]
open("/tmp/pf.json","w").write(json.dumps(case["rounds"]))
r = subprocess.run(["interp/target/release/lm","--profile",MAN,
    "--frames-file=/tmp/pf.json","--cap="+CAP], capture_output=True, text=True)
err=r.stderr
PAIR=re.compile(r"\(\((-?\d+), (-?\d+)\), (\d+)\)")
def sec(n):
    m=re.search(r"PROFILE %s=(\[.*?\])\n"%n, err, re.S); return m.group(1) if m else ""
cells=[(int(x),int(y),int(n)) for x,y,n in PAIR.findall(sec("cells"))]
stalls={(int(x),int(y)):int(n) for x,y,n in PAIR.findall(sec("stalls"))}
grid=open(MAN).read().split("\n")
rows=defaultdict(lambda:[0,0,0])
for x,y,n in cells:
    rows[y][0]+=n; rows[y][1]+=stalls.get((x,y),0); rows[y][2]+=1
print("row  exec  stall  ncells | line")
for y in sorted(rows):
    e,s,c=rows[y]
    line=grid[y] if y<len(grid) else ""
    print("%3d %6d %6d %4d | %s"%(y,e,s,c,line[:56]))
print("TOTAL exec", sum(v[0] for v in rows.values()), "stall", sum(v[1] for v in rows.values()))
