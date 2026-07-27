"""Sweep DX/DY/band-rects for solutions/matmul/build_dense.py.

Capacity floors are MEASURED (scratchpad/mm2/apfloor.py, ringsweep.py):
A queue >= 254 pipe cells, B ring >= 240.  Compaction shortens the lead/exit
corridors, so the snake rectangles must grow to hold the totals up.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
BUILD = os.path.join(REPO, 'solutions/matmul/build_dense.py')
OUT = '/tmp/dense'
os.makedirs(OUT, exist_ok=True)
AP_MIN, BR_MIN = 256, 242


def one(cfg):
    dx, dy, apw, aph, brw, brh = cfg
    f = f"{OUT}/d{dx}_{dy}_{apw}x{aph}_{brw}x{brh}.man"
    env = dict(os.environ, DX=str(dx), DY=str(dy), APW=str(apw), APH=str(aph),
               BRW=str(brw), BRH=str(brh))
    p = subprocess.run([sys.executable, BUILD, f], env=env,
                       capture_output=True, text=True)
    if p.returncode != 0:
        return None
    parts = p.stderr.strip().splitlines()[-1].split()
    w, h, box, nap, nbr = (int(v) for v in parts[1:6])
    if nap < AP_MIN or nbr < BR_MIN:
        return None
    return (box, w, h, nap, nbr, f, cfg)


cfgs = [(dx, dy, apw, aph, brw, brh)
        for dx in range(4, 9)
        for dy in range(2, 11)
        for apw in (14, 15)
        for aph in (16, 18, 20, 22)
        for brw in (18, 20)
        for brh in (10, 12)]
with ThreadPoolExecutor(max_workers=8) as ex:
    res = [r for r in ex.map(one, cfgs) if r]
res.sort()
seen = set()
best = []
for r in res:
    if r[0] in seen:
        continue
    seen.add(r[0])
    best.append(r)
for r in best[:8]:
    print(f"box={r[0]} {r[1]}x{r[2]} AP={r[3]} BR={r[4]} cfg={r[6]}")
print(f"-- {len(res)}/{len(cfgs)} viable")

for box, w, h, nap, nbr, f, cfg in best[:5]:
    p = subprocess.run([sys.executable, os.path.join(REPO, 'tools/grade_fast.py'),
                        'matmul', f], capture_output=True, text=True, cwd=REPO)
    try:
        d = json.loads(p.stdout)
    except Exception:
        print(f"{cfg} GRADE ERROR")
        continue
    print(f"cfg={cfg} box={box} pass={d['passed']}/{d['total']} "
          f"avg={d['avgTicks']} score={d['score']} -> {f}")
