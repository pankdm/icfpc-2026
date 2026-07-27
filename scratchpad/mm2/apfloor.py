"""Bisect the TRUE A-queue capacity floor.

DESIGN_mm2 derives "AP band must hold N*M <= 256" and sizes it 15x18 (+32 lead/exit
= 298 cells).  But AREL and the AR pipe also buffer values, so the real floor is
lower.  Build each band size, grade on the public cases with the Rust engine, print
pass/fail + ticks.  Non-monotonic degradation is expected, so report every point.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import build_mm2p as B  # noqa: E402

OUT = '/tmp/apfloor'
os.makedirs(OUT, exist_ok=True)

shapes = []
for arg in sys.argv[1:]:
    w, h = arg.split('x')
    shapes.append((int(w), int(h)))
if not shapes:
    shapes = [(15, 18), (15, 17), (15, 16), (14, 16), (13, 16), (13, 15), (12, 14),
              (11, 13), (10, 12), (8, 10), (6, 8)]

for w, h in shapes:
    tag = f"{w}x{h}"
    try:
        g, n_ap, n_br = B.build(ap_rect=(2, 2, w, h, False))
    except Exception as e:
        print(f"{tag:>7} band {w*h:3d}  BUILD FAIL {str(e)[:60]}", flush=True)
        continue
    path = os.path.join(OUT, f"ap{tag}.man")
    open(path, 'w').write(g.render() + "\n")
    fw, fh, box = g.footprint()
    p = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'grade_fast.py'),
                        'matmul', path], capture_output=True, text=True, timeout=1200)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
        st = f"{r['passed']}/{r['total']} avg {r['avgTicks']:.0f}"
    except Exception:
        st = "GRADE ERR " + (p.stdout + p.stderr)[-120:].replace('\n', ' ')
    print(f"{tag:>7} band {w*h:3d} AP={n_ap:3d} cells  {fw}x{fh} box {box}  {st}",
          flush=True)
